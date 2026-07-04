"""DTOs — objetos planos trocados entre Controllers e Views.

As Views nunca tocam em instâncias ORM (evita objetos destacados na UI e
mantém a GUI agnóstica à BD). Ver docs/MANUAL.md §3.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Option:
    """Entrada de dropdown (id pode ser None para '— nenhum —')."""

    id: int | None
    label: str


@dataclass
class DeviceRow:
    id: int
    hostname: str
    category: str
    location: str
    ip_mgmt: str
    mac: str
    vlan: str
    assigned_user: str
    status: str
    needs_relink: bool


@dataclass
class DeviceForm:
    hostname: str = ""
    category: str = "computador"
    template_id: int | None = None
    location_id: int | None = None
    status: str = "unknown"
    ip_mgmt: str = ""
    mac: str = ""
    vlan: str = ""
    os_detected: str = ""
    assigned_user: str = ""
    serial_number: str = ""
    notes: str = ""
    snmp_community: str = ""
    access_password: str = ""


@dataclass
class LocationRow:
    id: int
    name: str
    description: str
    parent: str


@dataclass
class LocationForm:
    name: str = ""
    description: str = ""
    parent_id: int | None = None


@dataclass
class TemplateRow:
    id: int
    name: str
    manufacturer: str
    model: str
    category: str
    port_count: int


@dataclass
class TemplateForm:
    name: str = ""
    manufacturer: str = ""
    model: str = ""
    category: str = "switch"
    port_count: int = 0
    port_speeds: str = "1G"
    port_prefix: str = "Port"
    is_passive: bool = False


@dataclass
class UserRow:
    id: int
    username: str
    full_name: str
    role: str
    is_active: bool


@dataclass
class UserForm:
    username: str = ""
    password: str = ""  # vazio na edição = manter a atual
    full_name: str = ""
    role: str = "maintenance"
    is_active: bool = True


@dataclass
class PortView:
    name: str
    speed: str
    status: str
    vlan: str
    connected_device: str
    connected_port: str
    user: str


@dataclass
class SynthesisView:
    hostname: str
    category: str
    location: str
    status: str
    template: str
    ports: list[PortView] = field(default_factory=list)


@dataclass
class SearchHit:
    device_id: int
    hostname: str
    category: str
    location: str
    matched_field: str
    matched_value: str
    connected_to: str
