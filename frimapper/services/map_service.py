"""Geração do mapa de topologia (diagrams + Graphviz) e alerta de staleness.

THREADING (ver DEVLOG #002): o contexto da ``diagrams`` é guardado em
variáveis thread-local — todo o bloco ``with Diagram()`` tem de correr NA
MESMA thread. Na GUI, ``generate()`` corre por inteiro num QThread dedicado
(``gui/views/main_window.MapWorker``), que abre a sua própria sessão de BD.

GERAÇÃO DIFERIDA: nada é desenhado durante o CRUD; só ao clicar "Gerar Mapa"
é que o SQLite é iterado e o grafo montado de uma vez.

ÍCONES (ver DEVLOG #005/#009): resolução em 3 níveis — PNG ``Custom`` próprio
(caminho ABSOLUTO, o Graphviz resolve ``image=`` no contexto de render) →
ícone nativo da diagrams (``NATIVE_FALLBACK``) → nó ``Blank``.
"""

from __future__ import annotations

import importlib
import os
import shutil
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from ..db.models import Device, Link, Location
from ..domain.enums import DeviceCategory, LinkType, PortStatus
from ..repositories.meta import get_meta, set_meta
from .bootstrap import AppContext


class MapGenerationError(RuntimeError):
    """Falha amigável na geração do mapa (ex.: Graphviz em falta)."""


#: Categorias incluídas na vista "core" (backbone).
CORE_CATEGORIES = {
    DeviceCategory.INTERNET,
    DeviceCategory.ROUTER,
    DeviceCategory.FIREWALL,
    DeviceCategory.SWITCH,
    DeviceCategory.SERVIDOR,
    DeviceCategory.NAS,
}

#: Categorias com badge Custom próprio (assets/icons/<categoria>.png).
ICON_FILES: dict[DeviceCategory, str] = {
    cat: f"{cat.value}.png"
    for cat in (
        DeviceCategory.UPS,
        DeviceCategory.IMPRESSORA,
        DeviceCategory.AP,
        DeviceCategory.REGUA,
        DeviceCategory.CABO_VAZIO,
        DeviceCategory.CAMARAS,
        DeviceCategory.CCTV,
        DeviceCategory.CONTROLO_ACESSOS,
        DeviceCategory.AUTOMATOS,
        DeviceCategory.SOLAR,
        DeviceCategory.CARREGADOR_EV,
        DeviceCategory.VOIP,
    )
}

#: Fallback para ícones nativos da diagrams: (módulo, classe).
NATIVE_FALLBACK: dict[DeviceCategory, tuple[str, str]] = {
    DeviceCategory.INTERNET: ("diagrams.onprem.network", "Internet"),
    DeviceCategory.ROUTER: ("diagrams.generic.network", "Router"),
    DeviceCategory.FIREWALL: ("diagrams.generic.network", "Firewall"),
    DeviceCategory.SWITCH: ("diagrams.generic.network", "Switch"),
    DeviceCategory.SERVIDOR: ("diagrams.onprem.compute", "Server"),
    DeviceCategory.NAS: ("diagrams.generic.storage", "Storage"),
    DeviceCategory.COMPUTADOR: ("diagrams.onprem.client", "Client"),
    DeviceCategory.PORTATIL: ("diagrams.onprem.client", "Client"),
    DeviceCategory.TELEFONE: ("diagrams.generic.device", "Mobile"),
    DeviceCategory.TELEFONE_FIXO: ("diagrams.generic.device", "Mobile"),
}


class MapService:
    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx

    # ------------------------------------------------------------ staleness
    def is_stale(self) -> bool:
        """True se a BD mudou depois da última geração do mapa.

        Comparação lexicográfica de timestamps ISO-8601 (ordenável como texto).
        """
        with self.ctx.db.session() as session:
            db_modified = get_meta(session, "db_last_modified", "")
            map_generated = get_meta(session, "map_last_generated", "")
        if not db_modified:
            return False
        if not map_generated:
            return True
        return db_modified > map_generated

    def last_map_path(self) -> str:
        with self.ctx.db.session() as session:
            return get_meta(session, "map_last_path", "")

    # ------------------------------------------------------------- geração
    def generate(self, view: str = "full", location_id: int | None = None) -> str:
        """Gera o PNG e devolve o caminho. Vistas: full | core | location."""
        try:
            from diagrams import Cluster, Diagram, Edge
            from diagrams.custom import Custom
            from diagrams.generic.blank import Blank
        except ImportError as exc:  # pragma: no cover
            raise MapGenerationError(
                "A biblioteca 'diagrams' não está instalada "
                "(pip install diagrams)."
            ) from exc
        if shutil.which("dot") is None:
            raise MapGenerationError(
                "Graphviz ('dot') não encontrado. Instale o Graphviz ou "
                "configure 'graphviz_dot_path' em config.ini."
            )

        timestamp = datetime.now()
        out_dir = Path(self.ctx.config.map_output)
        out_dir.mkdir(parents=True, exist_ok=True)
        stem = f"mapa_{view}_{timestamp:%Y%m%d_%H%M%S}"
        filename = str(out_dir / stem)
        title = f"Frimapper — vista '{view}' — {timestamp:%Y-%m-%d %H:%M:%S}"

        icon_dir = Path(self.ctx.config.icon_dir)

        def node_for(device: Device):
            label = f"{device.hostname}\n({device.category.value})"
            icon_name = ICON_FILES.get(device.category)
            if icon_name:
                icon_path = icon_dir / icon_name
                if icon_path.is_file():
                    # Caminho ABSOLUTO obrigatório (DEVLOG #009).
                    return Custom(label, os.path.abspath(icon_path))
            native = NATIVE_FALLBACK.get(device.category)
            if native:
                module = importlib.import_module(native[0])
                return getattr(module, native[1])(label)
            return Blank(label)

        with self.ctx.db.session() as session:
            devices = self._devices_for_view(session, view, location_id)
            device_ids = {d.id for d in devices}
            links = [
                link
                for link in session.scalars(select(Link))
                if link.port_a.device_id in device_ids
                and link.port_b.device_id in device_ids
            ]

            by_location: dict[str, list[Device]] = {}
            for device in devices:
                key = device.location.name if device.location else "Sem localização"
                by_location.setdefault(key, []).append(device)

            nodes: dict[int, object] = {}
            try:
                with Diagram(
                    title,
                    filename=filename,
                    show=False,
                    outformat="png",
                    graph_attr={
                        "fontsize": "18",
                        "splines": "spline",
                        "rankdir": "TB",
                    },
                ):
                    for location_name in sorted(by_location):
                        with Cluster(location_name):
                            for device in by_location[location_name]:
                                nodes[device.id] = node_for(device)
                    for link in links:
                        a = nodes[link.port_a.device_id]
                        b = nodes[link.port_b.device_id]
                        a - Edge(**self._edge_style(link)) - b
            except MapGenerationError:
                raise
            except Exception as exc:
                raise MapGenerationError(
                    f"Falha na geração do mapa (Graphviz): {exc}"
                ) from exc

        png_path = f"{filename}.png"
        with self.ctx.db.session() as session:
            set_meta(
                session,
                "map_last_generated",
                timestamp.isoformat(timespec="seconds"),
            )
            set_meta(session, "map_last_path", png_path)
        return png_path

    # ------------------------------------------------------------ internos
    @staticmethod
    def _edge_style(link: Link) -> dict:
        if link.status == PortStatus.DOWN:
            return {"color": "red", "style": "dashed", "label": "down"}
        if link.link_type == LinkType.PASSIVE:
            return {"color": "gray40", "style": "dotted"}
        return {"color": "black"}

    @staticmethod
    def _devices_for_view(
        session, view: str, location_id: int | None
    ) -> list[Device]:
        devices = list(session.scalars(select(Device).order_by(Device.hostname)))
        if view == "core":
            return [d for d in devices if d.category in CORE_CATEGORIES]
        if view == "location" and location_id is not None:
            wanted: set[int] = set()

            def collect(loc_id: int) -> None:
                wanted.add(loc_id)
                for child_id in session.scalars(
                    select(Location.id).where(Location.parent_id == loc_id)
                ):
                    collect(child_id)

            collect(location_id)
            return [d for d in devices if d.location_id in wanted]
        return devices
