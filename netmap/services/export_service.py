"""Exportação da base de dados para CSV (backup/leitura).

O SQLite é o único dono dos dados — a exportação é one-way. Os campos
cifrados NUNCA saem em claro: quando têm valor são substituídos por
``[protegido]`` (ver DEVLOG #006). Codificação ``utf-8-sig`` para abrir
diretamente no Excel.
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from ..db.models import Device, DeviceAttribute, DeviceTemplate, Link, Location, Port
from ..paths import data_dir
from .bootstrap import AppContext

PROTECTED_PLACEHOLDER = "[protegido]"


class ExportService:
    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx

    def export_all(self, out_dir: str | Path | None = None) -> list[str]:
        """Cria ``export_<timestamp>/`` com 6 CSV e devolve os caminhos."""
        base = Path(out_dir) if out_dir else data_dir()
        target = base / f"export_{datetime.now():%Y%m%d_%H%M%S}"
        target.mkdir(parents=True, exist_ok=True)
        files: list[str] = []
        with self.ctx.db.session() as session:
            files.append(self._locations(session, target))
            files.append(self._templates(session, target))
            files.append(self._devices(session, target))
            files.append(self._ports(session, target))
            files.append(self._links(session, target))
            files.append(self._attributes(session, target))
        if self.ctx.audit:
            self.ctx.audit.log("EXPORT", entity="csv", detail=str(target))
        return files

    @staticmethod
    def _write(path: Path, header: list[str], rows: list[list]) -> str:
        with open(path, "w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.writer(fh)
            writer.writerow(header)
            writer.writerows(rows)
        return str(path)

    def _locations(self, session, target: Path) -> str:
        rows = [
            [loc.id, loc.name, loc.description, loc.parent.name if loc.parent else ""]
            for loc in session.scalars(select(Location).order_by(Location.name))
        ]
        return self._write(
            target / "localizacoes.csv", ["id", "nome", "descricao", "zona_pai"], rows
        )

    def _templates(self, session, target: Path) -> str:
        rows = [
            [
                t.id, t.name, t.manufacturer, t.model, t.category.value,
                t.port_count, t.port_speeds, t.port_prefix, t.is_passive,
            ]
            for t in session.scalars(select(DeviceTemplate).order_by(DeviceTemplate.name))
        ]
        return self._write(
            target / "templates.csv",
            ["id", "nome", "fabricante", "modelo", "categoria",
             "n_portas", "velocidades", "prefixo_porta", "passivo"],
            rows,
        )

    def _devices(self, session, target: Path) -> str:
        rows = []
        for d in session.scalars(select(Device).order_by(Device.hostname)):
            rows.append(
                [
                    d.id, d.hostname, d.category.value,
                    d.template.name if d.template else "",
                    d.location.name if d.location else "",
                    d.status.value, d.ip_mgmt, d.mac, d.vlan, d.os_detected,
                    d.assigned_user, d.serial_number, d.notes,
                    PROTECTED_PLACEHOLDER if d.snmp_community else "",
                    PROTECTED_PLACEHOLDER if d.access_password else "",
                ]
            )
        return self._write(
            target / "equipamentos.csv",
            ["id", "hostname", "categoria", "modelo", "localizacao", "estado",
             "ip_gestao", "mac", "vlan", "so", "utilizador", "n_serie", "notas",
             "snmp_community", "password_acesso"],
            rows,
        )

    def _ports(self, session, target: Path) -> str:
        rows = [
            [p.id, p.device.hostname, p.name, p.speed, p.status.value, p.vlan, p.is_uplink]
            for p in session.scalars(select(Port).order_by(Port.device_id, Port.id))
        ]
        return self._write(
            target / "portas.csv",
            ["id", "equipamento", "porta", "velocidade", "estado", "vlan", "uplink"],
            rows,
        )

    def _links(self, session, target: Path) -> str:
        rows = [
            [
                l.id,
                l.port_a.device.hostname, l.port_a.name,
                l.port_b.device.hostname, l.port_b.name,
                l.link_type.value, l.status.value, l.notes,
            ]
            for l in session.scalars(select(Link).order_by(Link.id))
        ]
        return self._write(
            target / "ligacoes.csv",
            ["id", "equipamento_a", "porta_a", "equipamento_b", "porta_b",
             "tipo", "estado", "notas"],
            rows,
        )

    def _attributes(self, session, target: Path) -> str:
        rows = [
            [a.device.hostname, a.name, a.value]
            for a in session.scalars(
                select(DeviceAttribute).order_by(DeviceAttribute.device_id, DeviceAttribute.name)
            )
        ]
        return self._write(
            target / "campos_dinamicos.csv", ["equipamento", "campo", "valor"], rows
        )
