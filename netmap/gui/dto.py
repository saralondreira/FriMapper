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
class PortRow:
    id: int
    name: str
    speed: str
    status: str
    vlan: str
    is_uplink: bool
    connected_to: str


@dataclass
class PortForm:
    name: str = ""
    speed: str = ""
    vlan: str = ""
    is_uplink: bool = False


@dataclass
class LinkRow:
    id: int
    device_a: str
    port_a: str
    device_b: str
    port_b: str
    link_type: str
    status: str
    notes: str


@dataclass
class VlanRow:
    id: int
    vlan_id: int
    name: str
    description: str
    usage_count: int


@dataclass
class VlanForm:
    vlan_id: int = 1
    name: str = ""
    description: str = ""


@dataclass
class FirewallRow:
    id: int
    hostname: str
    location: str
    ip_mgmt: str
    status: str
    wan_ports: int


@dataclass
class MaintenanceRow:
    id: int
    hostname: str
    date: str
    next_due: str
    status: str
    technician: str
    description: str


@dataclass
class MaintenanceForm:
    device_id: int | None = None
    date: str = ""  # ISO (AAAA-MM-DD)
    next_due: str = ""  # ISO ou vazio
    status: str = "planned"
    technician: str = ""
    description: str = ""


@dataclass
class SearchHit:
    device_id: int
    hostname: str
    category: str
    location: str
    matched_field: str
    matched_value: str
    connected_to: str
