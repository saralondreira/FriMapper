"""Motor de pesquisa global.

Pesquisa por MAC, IP, nome de utilizador, hostname, VLAN, nº de série e
valores de campos dinâmicos; para cada resultado resolve em que
equipamento/porta o alvo está ligado. Todas as consultas são parametrizadas
via ORM (sem concatenação de strings — proteção contra SQL injection).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import or_, select

from ..db.models import Device, DeviceAttribute
from ..repositories.repositories import _link_for_port


@dataclass
class SearchResult:
    device_id: int
    hostname: str
    category: str
    location: str
    matched_field: str
    matched_value: str
    connected_to: str


class SearchService:
    def __init__(self, session) -> None:
        self.session = session

    def search(self, term: str) -> list[SearchResult]:
        term = (term or "").strip()
        if not term:
            return []
        pattern = f"%{term}%"
        found: dict[int, tuple[Device, str, str]] = {}

        fields = [
            ("hostname", Device.hostname),
            ("mac", Device.mac),
            ("ip_mgmt", Device.ip_mgmt),
            ("assigned_user", Device.assigned_user),
            ("vlan", Device.vlan),
            ("serial_number", Device.serial_number),
        ]
        for field_name, column in fields:
            for device in self.session.scalars(
                select(Device).where(column.ilike(pattern))
            ):
                found.setdefault(
                    device.id, (device, field_name, getattr(device, field_name) or "")
                )

        for attr in self.session.scalars(
            select(DeviceAttribute).where(
                or_(
                    DeviceAttribute.value.ilike(pattern),
                    DeviceAttribute.name.ilike(pattern),
                )
            )
        ):
            found.setdefault(attr.device_id, (attr.device, attr.name, attr.value))

        results = []
        for device, matched_field, matched_value in found.values():
            results.append(
                SearchResult(
                    device_id=device.id,
                    hostname=device.hostname,
                    category=device.category.value,
                    location=device.location.name if device.location else "",
                    matched_field=matched_field,
                    matched_value=matched_value,
                    connected_to=self._connection_summary(device),
                )
            )
        results.sort(key=lambda r: r.hostname.lower())
        return results

    def _connection_summary(self, device: Device) -> str:
        """Ex.: ``SW-A1:Gi0/3`` — onde o equipamento está ligado."""
        parts = []
        for port in device.ports:
            link = _link_for_port(self.session, port.id)
            if link is None:
                continue
            other = link.port_b if link.port_a_id == port.id else link.port_a
            parts.append(f"{other.device.hostname}:{other.name}")
        return "; ".join(parts)
