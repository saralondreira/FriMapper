"""Controller de autenticação."""

from __future__ import annotations

from ...services.bootstrap import AppContext
from ...services.user_service import UserService
from ..session import UserSession


class AuthController:
    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx
        self._users = UserService(ctx)

    def login(self, username: str, password: str) -> UserSession | None:
        user = self._users.authenticate(username, password)
        if user is None:
            return None
        self.ctx.audit.set_user(user.username)
        return UserSession(user_id=user.id, username=user.username, role=user.role)

    def verify_admin(self, username: str, password: str) -> bool:
        """Valida credenciais de Master (fluxo de force-delete)."""
        return self._users.verify_admin(username, password)
