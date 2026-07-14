"""Deteção de equipamentos órfãos após force-delete (ver DEVLOG #014).

Fluxo: ANTES do delete, ``link_peers()`` recolhe os equipamentos externos
ligados ao conjunto a eliminar; DEPOIS, ``mark_orphans()`` marca
``needs_relink=True`` nos que ficaram sem qualquer ligação e devolve os
hostnames para alertar na GUI. Criar uma nova ligação limpa o flag
(``LinkRepository.create``).
"""

from __future__ import annotations

from sqlalchemy import func, or_, select

from ..db.models import Device, Link, Location, Port


class IntegrityService:
    def __init__(self, session) -> None:
        self.session = session

    def device_ids_in_location(self, location_id: int) -> set[int]:
        """IDs de equipamentos numa zona, incluindo sub-zonas (recursivo)."""
        ids = set(
            self.session.scalars(
                select(Device.id).where(Device.location_id == location_id)
            )
        )
        for child_id in self.session.scalars(
            select(Location.id).where(Location.parent_id == location_id)
        ):
            ids |= self.device_ids_in_location(child_id)
        return ids

    def link_peers(self, device_ids: set[int]) -> set[int]:
        """Equipamentos EXTERNOS ligados a alguma porta do conjunto dado."""
        if not device_ids:
            return set()
        peers: set[int] = set()
        for link in self.session.scalars(select(Link)):
            dev_a = link.port_a.device_id
            dev_b = link.port_b.device_id
            if dev_a in device_ids and dev_b not in device_ids:
                peers.add(dev_b)
            if dev_b in device_ids and dev_a not in device_ids:
                peers.add(dev_a)
        return peers

    def has_no_links(self, device_id: int) -> bool:
        count = self.session.scalar(
            select(func.count())
            .select_from(Link)
            .join(Port, or_(Link.port_a_id == Port.id, Link.port_b_id == Port.id))
            .where(Port.device_id == device_id)
        )
        return not count

    def mark_orphans(self, device_ids: set[int]) -> list[str]:
        """Marca ``needs_relink`` nos equipamentos sem ligação; devolve hostnames."""
        orphans: list[str] = []
        for device_id in device_ids:
            device = self.session.get(Device, device_id)
            if device is None:
                continue
            if self.has_no_links(device_id):
                device.needs_relink = True
                orphans.append(device.hostname)
        self.session.flush()
        return sorted(orphans)

    def orphan_hostnames(self) -> list[str]:
        return sorted(
            self.session.scalars(
                select(Device.hostname).where(Device.needs_relink.is_(True))
            )
        )
