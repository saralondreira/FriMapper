"""Gestão de contas de utilizador e verificação de credenciais de Master."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from ..db.models import User
from ..domain.enums import Role
from ..repositories.base import DependencyError
from ..repositories.repositories import UserRepository
from ..security.auth import hash_password, needs_rehash, verify_password
from .bootstrap import AppContext


class UserService:
    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx

    def list_users(self) -> list[User]:
        with self.ctx.db.session() as session:
            return list(session.scalars(select(User).order_by(User.username)))

    def authenticate(self, username: str, password: str) -> User | None:
        """Valida credenciais; atualiza last_login e faz rehash transparente."""
        with self.ctx.db.session() as session:
            repo = UserRepository(session, self.ctx.audit)
            user = repo.by_username(username)
            if user is None or not user.is_active or not verify_password(
                password, user.password_hash
            ):
                self.ctx.audit.log("LOGIN_FAIL", entity="User", detail=username)
                return None
            if needs_rehash(user.password_hash):
                user.password_hash = hash_password(password)
            user.last_login = datetime.now()
            session.flush()
            self.ctx.audit.log("LOGIN_OK", entity="User", entity_id=user.id,
                               detail=username)
            return user

    def verify_admin(self, username: str, password: str) -> bool:
        """True apenas para credenciais válidas de um Master ativo.

        Usado no fluxo de force-delete (override por password de administrador).
        """
        with self.ctx.db.session() as session:
            repo = UserRepository(session, self.ctx.audit)
            user = repo.by_username(username)
            return (
                user is not None
                and user.is_active
                and user.role == Role.MASTER
                and verify_password(password, user.password_hash)
            )

    def create_user(
        self, username: str, password: str, full_name: str, role: Role
    ) -> User:
        username = (username or "").strip()
        if not username:
            raise ValueError("O nome de utilizador é obrigatório.")
        if not password:
            raise ValueError("A password é obrigatória.")
        with self.ctx.db.session() as session:
            repo = UserRepository(session, self.ctx.audit)
            if repo.by_username(username) is not None:
                raise ValueError(f"O utilizador '{username}' já existe.")
            return repo.add(
                User(
                    username=username,
                    password_hash=hash_password(password),
                    full_name=full_name or "",
                    role=role,
                )
            )

    def set_password(self, user_id: int, new_password: str) -> None:
        if not new_password:
            raise ValueError("A password não pode ser vazia.")
        with self.ctx.db.session() as session:
            repo = UserRepository(session, self.ctx.audit)
            user = repo.get(user_id)
            repo.update(user, password_hash=hash_password(new_password))

    def set_role(self, user_id: int, role: Role) -> None:
        with self.ctx.db.session() as session:
            repo = UserRepository(session, self.ctx.audit)
            user = repo.get(user_id)
            if user.role == Role.MASTER and role != Role.MASTER and repo.dependencies(user):
                raise ValueError("Não é possível despromover o único Master ativo.")
            repo.update(user, role=role)

    def set_active(self, user_id: int, active: bool) -> None:
        with self.ctx.db.session() as session:
            repo = UserRepository(session, self.ctx.audit)
            user = repo.get(user_id)
            if not active and repo.dependencies(user):
                raise ValueError("Não é possível desativar o único Master ativo.")
            repo.update(user, is_active=active)

    def delete_user(self, user_id: int) -> None:
        with self.ctx.db.session() as session:
            repo = UserRepository(session, self.ctx.audit)
            user = repo.get(user_id)
            repo.delete(user)  # DependencyError se for o único Master ativo
