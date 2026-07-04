"""Controller de equipamentos: CRUD, campos dinâmicos, síntese e órfãos."""

from __future__ import annotations

from sqlalchemy import select

from ...db.models import Device, DeviceTemplate, Location
from ...domain.enums import DeviceCategory, DeviceStatus
from ...repositories.repositories import DeviceRepository, TemplateRepository
from ...security.rbac import Permission
from ...services.integrity_service import IntegrityService
from ...services.synthesis_service import SynthesisService
from ..dto import DeviceForm, DeviceRow, Option, PortView, SynthesisView
from .base import BaseController


class DeviceController(BaseController):
    # ------------------------------------------------------------ leitura
    def list_devices(self) -> list[DeviceRow]:
        self._require(Permission.VIEW)
        with self.ctx.db.session() as s:
            rows = []
            for d in s.scalars(select(Device).order_by(Device.hostname)):
                rows.append(
                    DeviceRow(
                        id=d.id,
                        hostname=d.hostname,
                        category=d.category.value,
                        location=d.location.name if d.location else "",
                        ip_mgmt=d.ip_mgmt or "",
                        mac=d.mac or "",
                        vlan=d.vlan or "",
                        assigned_user=d.assigned_user or "",
                        status=d.status.value,
                        needs_relink=d.needs_relink,
                    )
                )
            return rows

    def orphan_hostnames(self) -> list[str]:
        with self.ctx.db.session() as s:
            return IntegrityService(s).orphan_hostnames()

    def template_options(self) -> list[Option]:
        with self.ctx.db.session() as s:
            options = [Option(None, "— sem modelo —")]
            for t in s.scalars(select(DeviceTemplate).order_by(DeviceTemplate.name)):
                options.append(Option(t.id, f"{t.name} ({t.port_count} portas)"))
            return options

    def location_options(self) -> list[Option]:
        with self.ctx.db.session() as s:
            options = [Option(None, "— sem localização —")]
            for loc in s.scalars(select(Location).order_by(Location.name)):
                options.append(Option(loc.id, loc.name))
            return options

    def get_form(self, device_id: int) -> DeviceForm:
        with self.ctx.db.session() as s:
            d = s.get(Device, device_id)
            return DeviceForm(
                hostname=d.hostname,
                category=d.category.value,
                template_id=d.template_id,
                location_id=d.location_id,
                status=d.status.value,
                ip_mgmt=d.ip_mgmt or "",
                mac=d.mac or "",
                vlan=d.vlan or "",
                os_detected=d.os_detected or "",
                assigned_user=d.assigned_user or "",
                serial_number=d.serial_number or "",
                notes=d.notes or "",
                snmp_community=d.snmp_community or "",
                access_password=d.access_password or "",
            )

    # ------------------------------------------------------------ escrita
    def create(self, form: DeviceForm) -> int:
        self._require(Permission.CREATE)
        if not form.hostname.strip():
            raise ValueError("O hostname é obrigatório.")
        with self.ctx.db.session() as s:
            repo = DeviceRepository(s, self.ctx.audit)
            if repo.by_hostname(form.hostname.strip()) is not None:
                raise ValueError(f"Já existe um equipamento '{form.hostname}'.")
            template = None
            if form.template_id is not None:
                template = TemplateRepository(s, self.ctx.audit).get(form.template_id)
            device = repo.create_from_template(
                form.hostname.strip(),
                template,
                **self._fields(form, with_category=template is None),
            )
            return device.id

    def update(self, device_id: int, form: DeviceForm) -> None:
        self._require(Permission.EDIT)
        with self.ctx.db.session() as s:
            repo = DeviceRepository(s, self.ctx.audit)
            device = repo.get(device_id)
            repo.update(
                device,
                hostname=form.hostname.strip(),
                **self._fields(form, with_category=True),
            )

    def delete(self, device_id: int, force: bool = False) -> list[str]:
        """Elimina; devolve os hostnames que ficaram órfãos (só com force)."""
        self._require(Permission.FORCE_DELETE if force else Permission.DELETE)
        with self.ctx.db.session() as s:
            repo = DeviceRepository(s, self.ctx.audit)
            integrity = IntegrityService(s)
            device = repo.get(device_id)
            peers = integrity.link_peers({device_id}) if force else set()
            repo.delete(device, force=force)  # DependencyError propaga p/ a View
            return integrity.mark_orphans(peers) if force else []

    # ------------------------------------------------- campos dinâmicos
    def get_attributes(self, device_id: int) -> list[tuple[str, str]]:
        with self.ctx.db.session() as s:
            repo = DeviceRepository(s, self.ctx.audit)
            device = repo.get(device_id)
            return [(a.name, a.value) for a in repo.attributes(device)]

    def save_attributes(self, device_id: int, pairs: list[tuple[str, str]]) -> None:
        self._require(Permission.EDIT)
        with self.ctx.db.session() as s:
            repo = DeviceRepository(s, self.ctx.audit)
            repo.set_attributes(repo.get(device_id), pairs)

    # ------------------------------------------------------------ síntese
    def synthesis(self, device_id: int) -> SynthesisView:
        self._require(Permission.VIEW)
        with self.ctx.db.session() as s:
            device = s.get(Device, device_id)
            node = SynthesisService(s).for_device(device)
            return SynthesisView(
                hostname=node.hostname,
                category=node.category,
                location=node.location,
                status=node.status,
                template=node.template,
                ports=[
                    PortView(
                        name=p.name,
                        speed=p.speed,
                        status=p.status,
                        vlan=p.vlan,
                        connected_device=p.connected_device,
                        connected_port=p.connected_port,
                        user=p.user,
                    )
                    for p in node.ports
                ],
            )

    # ------------------------------------------------------------ interno
    @staticmethod
    def _fields(form: DeviceForm, with_category: bool) -> dict:
        fields = {
            "location_id": form.location_id,
            "status": DeviceStatus(form.status),
            "ip_mgmt": form.ip_mgmt,
            "mac": form.mac,
            "vlan": form.vlan,
            "os_detected": form.os_detected,
            "assigned_user": form.assigned_user,
            "serial_number": form.serial_number,
            "notes": form.notes,
            "snmp_community": form.snmp_community or None,
            "access_password": form.access_password or None,
        }
        if with_category:
            fields["category"] = DeviceCategory(form.category)
        return fields
