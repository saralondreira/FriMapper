"""Base dos controllers: gestão de sessões de BD e verificação RBAC."""

from __future__ import annotations

from ...security.rbac import Permission
from ...services.bootstrap import AppContext
from ..session import UserSession


class ControllerPermissionError(PermissionError):
    """Operação recusada pelo RBAC (defesa em profundidade além da GUI)."""


class BaseController:
    def __init__(self, ctx: AppContext, session: UserSession) -> None:
        self.ctx = ctx
        self.user = session

    def _require(self, permission: Permission) -> None:
        if not self.user.can(permission):
            raise ControllerPermissionError(
                f"O perfil '{self.user.role.value}' não tem permissão "
                f"{permission.name}."
            )
