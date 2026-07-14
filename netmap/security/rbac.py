"""RBAC — permissões por perfil e data masking ao nível do campo.

Perfis (ver docs/MANUAL.md §9):
- MASTER      — acesso total (inclui force-delete e gestão de utilizadores).
- TECH        — CRUD, mapas e export; sem gestão de utilizadores.
- MAINTENANCE — só leitura, com masking dos campos sensíveis.
"""

from __future__ import annotations

from enum import Enum, auto

from ..domain.enums import Role


class Permission(Enum):
    VIEW = auto()
    CREATE = auto()
    EDIT = auto()
    DELETE = auto()
    FORCE_DELETE = auto()
    MANAGE_USERS = auto()
    GENERATE_MAP = auto()
    EXPORT = auto()


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.MASTER: frozenset(Permission),
    Role.TECH: frozenset(
        {
            Permission.VIEW,
            Permission.CREATE,
            Permission.EDIT,
            Permission.DELETE,
            Permission.GENERATE_MAP,
            Permission.EXPORT,
        }
    ),
    Role.MAINTENANCE: frozenset({Permission.VIEW}),
}

#: Campos apresentados como ``***`` ao perfil MAINTENANCE.
SENSITIVE_FIELDS: frozenset[str] = frozenset(
    {
        "ip_mgmt",
        "mac",
        "vlan",
        "os_detected",
        "snmp_community",
        "access_password",
        "serial_number",
    }
)

MASK = "***"


def has_permission(role: Role, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, frozenset())


def is_field_masked(role: Role, field: str) -> bool:
    return role == Role.MAINTENANCE and field in SENSITIVE_FIELDS


def mask_value(role: Role, field: str, value):
    """Devolve ``***`` se o campo for sensível para o perfil; senão o valor."""
    if value in (None, "") or not is_field_masked(role, field):
        return value
    return MASK
