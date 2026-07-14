"""Controller de portas de um equipamento (CRUD dedicado)."""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError

from ...db.models import Device, Port
from ...repositories.repositories import (
    DeviceRepository,
    PortRepository,
    _link_for_port,
)
from ...security.rbac import Permission, mask_value
from ..dto import PortForm, PortRow
from .base import BaseController


class PortController(BaseController):
    def list_rows(self, device_id: int) -> list[PortRow]:
        self._require(Permission.VIEW)
        with self.ctx.db.session() as s:
            device = s.get(Device, device_id)
            rows = []
            for port in device.ports:
                link = _link_for_port(s, port.id)
                connected = ""
                if link is not None:
                    other = link.port_b if link.port_a_id == port.id else link.port_a
                    connected = f"{other.device.hostname}:{other.name}"
                rows.append(
                    PortRow(
                        id=port.id,
                        name=port.name,
                        speed=port.speed or "",
                        status=port.status.value,
                        vlan=mask_value(self.user.role, "vlan", port.vlan or "") or "",
                        is_uplink=port.is_uplink,
                        connected_to=connected,
                    )
                )
            return rows

    def get_form(self, port_id: int) -> PortForm:
        with self.ctx.db.session() as s:
            port = s.get(Port, port_id)
            return PortForm(
                name=port.name,
                speed=port.speed or "",
                vlan=port.vlan or "",
                is_uplink=port.is_uplink,
            )

    def create(self, device_id: int, form: PortForm) -> int:
        self._require(Permission.CREATE)
        if not form.name.strip():
            raise ValueError("O nome da porta é obrigatório.")
        with self.ctx.db.session() as s:
            repo = DeviceRepository(s, self.ctx.audit)
            device = repo.get(device_id)
            try:
                port = repo.add_manual_port(
                    device,
                    form.name.strip(),
                    form.speed,
                    vlan=form.vlan,
                    is_uplink=form.is_uplink,
                )
                s.flush()
            except IntegrityError as exc:
                raise ValueError(
                    f"O equipamento já tem uma porta '{form.name}'."
                ) from exc
            return port.id

    def update(self, port_id: int, form: PortForm) -> None:
        self._require(Permission.EDIT)
        if not form.name.strip():
            raise ValueError("O nome da porta é obrigatório.")
        with self.ctx.db.session() as s:
            repo = PortRepository(s, self.ctx.audit)
            try:
                repo.update(
                    repo.get(port_id),
                    name=form.name.strip(),
                    speed=form.speed,
                    vlan=form.vlan,
                    is_uplink=form.is_uplink,
                )
            except IntegrityError as exc:
                raise ValueError(
                    f"O equipamento já tem uma porta '{form.name}'."
                ) from exc

    def delete(self, port_id: int, force: bool = False) -> list[str]:
        """Bloqueada se tiver ligação (DependencyError propaga para a View)."""
        self._require(Permission.FORCE_DELETE if force else Permission.DELETE)
        with self.ctx.db.session() as s:
            repo = PortRepository(s, self.ctx.audit)
            repo.delete(repo.get(port_id), force=force)
            return []
