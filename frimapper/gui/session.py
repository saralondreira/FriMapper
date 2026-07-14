"""Sessão de utilizador da GUI — apenas valores, sem instâncias ORM."""

from __future__ import annotations

from dataclasses import dataclass

from ..domain.enums import Role
from ..security.rbac import Permission, has_permission


@dataclass
class UserSession:
    user_id: int
    username: str
    role: Role

    def can(self, permission: Permission) -> bool:
        return has_permission(self.role, permission)
