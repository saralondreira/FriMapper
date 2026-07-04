"""Controller de gestão de utilizadores (apenas Master)."""

from __future__ import annotations

from ...domain.enums import Role
from ...security.rbac import Permission
from ...services.user_service import UserService
from ..dto import UserForm, UserRow
from .base import BaseController


class UserController(BaseController):
    def __init__(self, ctx, session) -> None:
        super().__init__(ctx, session)
        self._users = UserService(ctx)

    def list_rows(self) -> list[UserRow]:
        self._require(Permission.MANAGE_USERS)
        return [
            UserRow(
                id=u.id,
                username=u.username,
                full_name=u.full_name or "",
                role=u.role.value,
                is_active=u.is_active,
            )
            for u in self._users.list_users()
        ]

    def get_form(self, user_id: int) -> UserForm:
        self._require(Permission.MANAGE_USERS)
        for u in self._users.list_users():
            if u.id == user_id:
                return UserForm(
                    username=u.username,
                    password="",
                    full_name=u.full_name or "",
                    role=u.role.value,
                    is_active=u.is_active,
                )
        raise ValueError(f"Utilizador {user_id} inexistente.")

    def create(self, form: UserForm) -> int:
        self._require(Permission.MANAGE_USERS)
        user = self._users.create_user(
            form.username, form.password, form.full_name, Role(form.role)
        )
        return user.id

    def update(self, user_id: int, form: UserForm) -> None:
        self._require(Permission.MANAGE_USERS)
        if form.password:
            self._users.set_password(user_id, form.password)
        self._users.set_role(user_id, Role(form.role))
        self._users.set_active(user_id, form.is_active)

    def delete(self, user_id: int, force: bool = False) -> list[str]:
        self._require(Permission.MANAGE_USERS)
        self._users.delete_user(user_id)  # o último Master nunca é eliminável
        return []
