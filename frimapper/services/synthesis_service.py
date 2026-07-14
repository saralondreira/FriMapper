"""Painel de síntese por nó: portas, o que está ligado, utilizador, VLAN, estado."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..db.models import Device
from ..repositories.repositories import _link_for_port


@dataclass
class PortSynthesis:
    name: str
    speed: str
    status: str
    vlan: str
    connected_device: str
    connected_port: str
    user: str


@dataclass
class NodeSynthesis:
    hostname: str
    category: str
    location: str
    status: str
    template: str
    ports: list[PortSynthesis] = field(default_factory=list)


class SynthesisService:
    def __init__(self, session) -> None:
        self.session = session

    def for_device(self, device: Device) -> NodeSynthesis:
        ports: list[PortSynthesis] = []
        for port in device.ports:
            connected_device = connected_port = user = ""
            status = port.status.value
            link = _link_for_port(self.session, port.id)
            if link is not None:
                other = link.port_b if link.port_a_id == port.id else link.port_a
                connected_device = other.device.hostname
                connected_port = other.name
                user = other.device.assigned_user or ""
                status = link.status.value
            ports.append(
                PortSynthesis(
                    name=port.name,
                    speed=port.speed or "",
                    status=status,
                    vlan=port.vlan or "",
                    connected_device=connected_device,
                    connected_port=connected_port,
                    user=user,
                )
            )
        return NodeSynthesis(
            hostname=device.hostname,
            category=device.category.value,
            location=device.location.name if device.location else "",
            status=device.status.value,
            template=device.template.name if device.template else "",
            ports=ports,
        )
