"""Controller de ligações — os dropdowns só expõem portas LIVRES."""

from __future__ import annotations

from sqlalchemy import select

from ...db.models import Device, Link, Port
from ...domain.enums import PortStatus
from ...repositories.repositories import DeviceRepository, LinkRepository
from ...security.rbac import Permission
from ..dto import LinkRow, Option
from .base import BaseController


class LinkController(BaseController):
    def list_rows(self) -> list[LinkRow]:
        self._require(Permission.VIEW)
        with self.ctx.db.session() as s:
            return [
                LinkRow(
                    id=link.id,
                    device_a=link.port_a.device.hostname,
                    port_a=link.port_a.name,
                    device_b=link.port_b.device.hostname,
                    port_b=link.port_b.name,
                    link_type=link.link_type.value,
                    status=link.status.value,
                    notes=link.notes or "",
                )
                for link in s.scalars(select(Link).order_by(Link.id))
            ]

    def set_status(self, link_id: int, down: bool, notes: str | None = None) -> None:
        self._require(Permission.EDIT)
        with self.ctx.db.session() as s:
            repo = LinkRepository(s, self.ctx.audit)
            repo.set_status(
                repo.get(link_id),
                PortStatus.DOWN if down else PortStatus.UP,
                notes=notes,
            )

    def delete(self, link_id: int, force: bool = False) -> list[str]:
        """Eliminar uma ligação liberta as duas portas (status UNUSED)."""
        self._require(Permission.DELETE)
        with self.ctx.db.session() as s:
            repo = LinkRepository(s, self.ctx.audit)
            repo.delete(repo.get(link_id))
            return []

    def form_data(self) -> tuple[list[Option], dict[int, list[Option]]]:
        """(equipamentos, {device_id: portas livres}) para o LinkDialog."""
        self._require(Permission.VIEW)
        with self.ctx.db.session() as s:
            repo = DeviceRepository(s, self.ctx.audit)
            devices: list[Option] = []
            free_ports: dict[int, list[Option]] = {}
            for device in s.scalars(select(Device).order_by(Device.hostname)):
                ports = [
                    Option(p.id, f"{p.name} ({p.speed})" if p.speed else p.name)
                    for p in repo.free_ports(device)
                ]
                if ports:
                    devices.append(Option(device.id, device.hostname))
                    free_ports[device.id] = ports
            return devices, free_ports

    def create(self, port_a_id: int, port_b_id: int, down: bool = False) -> None:
        self._require(Permission.CREATE)
        with self.ctx.db.session() as s:
            repo = LinkRepository(s, self.ctx.audit)
            port_a = s.get(Port, port_a_id)
            port_b = s.get(Port, port_b_id)
            repo.create(
                port_a,
                port_b,
                status=PortStatus.DOWN if down else PortStatus.UP,
            )
