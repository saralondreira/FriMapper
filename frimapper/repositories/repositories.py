"""Repositórios concretos com regras de dependência e cascata.

| Entidade       | Bloqueio (dependencies)            | Cascata (force)                  |
|----------------|------------------------------------|----------------------------------|
| Location       | equipamentos na zona; sub-zonas    | apaga equipamentos e sub-zonas   |
| DeviceTemplate | equipamentos que usam o modelo     | desassocia (template_id=None)    |
| Device         | portas ocupadas (com link)         | remove links; ports caem por ORM |
| Port           | tem link                           | remove o link                    |
| User           | é o único Master ativo             | — (nunca permitido)              |
"""

from __future__ import annotations

from sqlalchemy import or_, select

from ..db.models import (
    Device,
    DeviceAttribute,
    DeviceTemplate,
    Link,
    Location,
    MaintenanceRecord,
    Port,
    User,
    Vlan,
)
from ..domain.enums import LinkType, PortStatus, Role
from .base import BaseRepository, DependencyError


def _link_for_port(session, port_id: int) -> Link | None:
    return session.scalar(
        select(Link).where(or_(Link.port_a_id == port_id, Link.port_b_id == port_id))
    )


def _remove_link(session, link: Link) -> None:
    """Apaga um link repondo o estado das portas sobreviventes a UNUSED."""
    for port in (link.port_a, link.port_b):
        if port is not None:
            port.status = PortStatus.UNUSED
    session.delete(link)


class UserRepository(BaseRepository):
    model = User
    entity_name = "User"

    def by_username(self, username: str) -> User | None:
        return self.session.scalar(select(User).where(User.username == username))

    def dependencies(self, user: User) -> list[str]:
        if user.role == Role.MASTER and user.is_active:
            other_masters = self.session.scalars(
                select(User).where(
                    User.role == Role.MASTER,
                    User.is_active.is_(True),
                    User.id != user.id,
                )
            ).first()
            if other_masters is None:
                return ["é o único utilizador Master ativo"]
        return []

    def delete(self, obj: User, force: bool = False) -> None:
        # O último Master ativo NUNCA pode ser eliminado — nem com force.
        deps = self.dependencies(obj)
        if deps:
            raise DependencyError(
                "O único Master ativo não pode ser eliminado.", deps
            )
        super().delete(obj, force=False)


class LocationRepository(BaseRepository):
    model = Location
    entity_name = "Location"

    # As dependências são sempre consultadas à BD (as coleções ORM podem
    # estar desatualizadas se foram carregadas antes de novas inserções).
    def _devices_of(self, location: Location) -> list[Device]:
        return list(
            self.session.scalars(
                select(Device).where(Device.location_id == location.id)
            )
        )

    def _children_of(self, location: Location) -> list[Location]:
        return list(
            self.session.scalars(
                select(Location).where(Location.parent_id == location.id)
            )
        )

    def dependencies(self, location: Location) -> list[str]:
        deps = [f"equipamento: {d.hostname}" for d in self._devices_of(location)]
        deps += [f"sub-zona: {c.name}" for c in self._children_of(location)]
        return deps

    def _cascade(self, location: Location) -> None:
        device_repo = DeviceRepository(self.session, self.audit)
        for child in self._children_of(location):
            self._cascade(child)
            self.session.delete(child)
        for device in self._devices_of(location):
            device_repo._cascade(device)
            self.session.delete(device)
        self.session.flush()


class TemplateRepository(BaseRepository):
    model = DeviceTemplate
    entity_name = "DeviceTemplate"

    def _devices_of(self, template: DeviceTemplate) -> list[Device]:
        return list(
            self.session.scalars(
                select(Device).where(Device.template_id == template.id)
            )
        )

    def dependencies(self, template: DeviceTemplate) -> list[str]:
        return [f"equipamento: {d.hostname}" for d in self._devices_of(template)]

    def _cascade(self, template: DeviceTemplate) -> None:
        # O force-delete de um modelo não destrói equipamentos: desassocia-os.
        for device in self._devices_of(template):
            device.template_id = None
            device.template = None
        self.session.flush()


class DeviceRepository(BaseRepository):
    model = Device
    entity_name = "Device"

    def by_hostname(self, hostname: str) -> Device | None:
        return self.session.scalar(select(Device).where(Device.hostname == hostname))

    def create_from_template(
        self, hostname: str, template: DeviceTemplate | None = None, **fields
    ) -> Device:
        """Cria um equipamento; com modelo, herda categoria e portas."""
        device = Device(hostname=hostname, **fields)
        if template is not None:
            device.template_id = template.id
            device.category = template.category
            speeds = [s.strip() for s in (template.port_speeds or "").split(",") if s.strip()]
            prefix = template.port_prefix or "Port"
            for i in range(1, (template.port_count or 0) + 1):
                speed = speeds[min(i - 1, len(speeds) - 1)] if speeds else ""
                device.ports.append(Port(name=f"{prefix}{i}", speed=speed))
        return self.add(device)

    def add_manual_port(self, device: Device, name: str, speed: str = "", **kw) -> Port:
        port = Port(device_id=device.id, name=name, speed=speed, **kw)
        self.session.add(port)
        self.session.flush()
        self._touch_db()
        if self.audit:
            self.audit.log(
                "CREATE", entity="Port", entity_id=port.id,
                detail=f"{device.hostname}:{name}",
            )
        return port

    def occupied_ports(self, device: Device) -> list[Port]:
        return [p for p in device.ports if _link_for_port(self.session, p.id)]

    def free_ports(self, device: Device) -> list[Port]:
        return [p for p in device.ports if _link_for_port(self.session, p.id) is None]

    def attributes(self, device: Device) -> list[DeviceAttribute]:
        return sorted(device.attributes, key=lambda a: a.name.lower())

    def set_attributes(self, device: Device, pairs: list[tuple[str, str]]) -> None:
        """Sincroniza os campos dinâmicos: adiciona, atualiza e remove ausentes."""
        wanted = {name.strip(): value for name, value in pairs if name.strip()}
        existing = {attr.name: attr for attr in device.attributes}
        for name, attr in existing.items():
            if name not in wanted:
                # Remover da coleção aciona o delete-orphan do ORM.
                device.attributes.remove(attr)
            elif attr.value != wanted[name]:
                attr.value = wanted[name]
        for name, value in wanted.items():
            if name not in existing:
                device.attributes.append(DeviceAttribute(name=name, value=value))
        self.session.flush()
        self._touch_db()
        self._audit("UPDATE", device, detail="campos dinâmicos")

    def dependencies(self, device: Device) -> list[str]:
        return [f"porta ligada: {p.name}" for p in self.occupied_ports(device)]

    def _cascade(self, device: Device) -> None:
        for port in device.ports:
            link = _link_for_port(self.session, port.id)
            if link is not None:
                _remove_link(self.session, link)
        self.session.flush()


class PortRepository(BaseRepository):
    model = Port
    entity_name = "Port"

    def dependencies(self, port: Port) -> list[str]:
        link = _link_for_port(self.session, port.id)
        return ["ligação existente"] if link is not None else []

    def _cascade(self, port: Port) -> None:
        link = _link_for_port(self.session, port.id)
        if link is not None:
            _remove_link(self.session, link)
        self.session.flush()


class LinkRepository(BaseRepository):
    model = Link
    entity_name = "Link"

    def create(
        self,
        port_a: Port,
        port_b: Port,
        link_type: LinkType = LinkType.ACTIVE,
        status: PortStatus = PortStatus.UP,
        notes: str = "",
    ) -> Link:
        """Cria uma ligação entre duas portas LIVRES.

        Define o estado das portas e limpa ``needs_relink`` de ambos os
        equipamentos (reposição de órfãos — ver DEVLOG #014).
        """
        if port_a.id == port_b.id:
            raise ValueError("Uma porta não pode ser ligada a si própria.")
        for port in (port_a, port_b):
            if _link_for_port(self.session, port.id) is not None:
                raise ValueError(
                    f"A porta {port.device.hostname}:{port.name} já está ocupada."
                )
        link = Link(
            port_a_id=port_a.id,
            port_b_id=port_b.id,
            link_type=link_type,
            status=status,
            notes=notes,
        )
        self.session.add(link)
        port_status = PortStatus.UP if status == PortStatus.UP else PortStatus.DOWN
        port_a.status = port_status
        port_b.status = port_status
        port_a.device.needs_relink = False
        port_b.device.needs_relink = False
        self.session.flush()
        self._touch_db()
        if self.audit:
            self.audit.log(
                "CREATE",
                entity="Link",
                entity_id=link.id,
                detail=(
                    f"{port_a.device.hostname}:{port_a.name} <-> "
                    f"{port_b.device.hostname}:{port_b.name}"
                ),
            )
        return link

    def set_status(self, link: Link, status: PortStatus, notes: str | None = None) -> None:
        """Muda o estado da ligação (up/down) refletindo-o nas portas."""
        link.status = status
        port_status = PortStatus.UP if status == PortStatus.UP else PortStatus.DOWN
        link.port_a.status = port_status
        link.port_b.status = port_status
        if notes is not None:
            link.notes = notes
        self.session.flush()
        self._touch_db()
        if self.audit:
            self.audit.log(
                "UPDATE", entity="Link", entity_id=link.id,
                detail=f"status={status.value}",
            )

    def dependencies(self, link: Link) -> list[str]:
        return []

    def delete(self, obj: Link, force: bool = False) -> None:
        _remove_link(self.session, obj)
        self.session.flush()
        self._touch_db()
        if self.audit:
            self.audit.log("DELETE", entity="Link", entity_id=obj.id)


class VlanRepository(BaseRepository):
    model = Vlan
    entity_name = "Vlan"

    def by_vlan_id(self, vlan_id: int) -> Vlan | None:
        return self.session.scalar(select(Vlan).where(Vlan.vlan_id == vlan_id))

    def _users_of(self, vlan: Vlan) -> tuple[list[Device], list[Port]]:
        """Equipamentos/portas cujo campo texto corresponde a str(vlan_id)."""
        tag = str(vlan.vlan_id)
        devices = list(self.session.scalars(select(Device).where(Device.vlan == tag)))
        ports = list(self.session.scalars(select(Port).where(Port.vlan == tag)))
        return devices, ports

    def dependencies(self, vlan: Vlan) -> list[str]:
        devices, ports = self._users_of(vlan)
        deps = [f"equipamento: {d.hostname}" for d in devices]
        deps += [f"porta: {p.device.hostname}:{p.name}" for p in ports]
        return deps

    def _cascade(self, vlan: Vlan) -> None:
        # O force-delete não destrói equipamentos: limpa o campo VLAN neles.
        devices, ports = self._users_of(vlan)
        for device in devices:
            device.vlan = ""
        for port in ports:
            port.vlan = ""
        self.session.flush()


class MaintenanceRepository(BaseRepository):
    model = MaintenanceRecord
    entity_name = "Maintenance"

    def for_device(self, device_id: int) -> list[MaintenanceRecord]:
        return list(
            self.session.scalars(
                select(MaintenanceRecord)
                .where(MaintenanceRecord.device_id == device_id)
                .order_by(MaintenanceRecord.date.desc())
            )
        )

    def _audit(self, action: str, obj: MaintenanceRecord, detail: str = "") -> None:
        if self.audit is None:
            return
        hostname = obj.device.hostname if obj.device else obj.device_id
        self.audit.log(
            action,
            entity=self.entity_name,
            entity_id=getattr(obj, "id", None),
            detail=f"{hostname} {obj.date} {detail}".strip(),
        )
