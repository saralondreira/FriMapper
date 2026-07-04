"""Repositório base: única via de escrita na BD.

Regras transversais:
- ``delete()`` sem ``force`` levanta ``DependencyError`` quando a entidade
  tem dependências (integridade estrita — só atualização é permitida).
- ``force=True`` (validado na GUI com password de Master) corre a cascata e
  regista ``FORCE_DELETE`` na auditoria.
- Toda a escrita atualiza ``db_last_modified`` (alerta de mapa desatualizado)
  e é auditada.
- Unit of Work: os repositórios fazem ``flush``; o ``commit`` pertence ao
  controller/serviço que abriu a sessão.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..security.audit import AuditLogger
from .meta import set_meta


class DependencyError(Exception):
    """Eliminação bloqueada por dependências."""

    def __init__(self, message: str, dependencies: list[str]) -> None:
        super().__init__(message)
        self.dependencies = list(dependencies)


class BaseRepository:
    model = None
    entity_name = "?"

    def __init__(self, session: Session, audit: AuditLogger | None = None) -> None:
        self.session = session
        self.audit = audit

    # ------------------------------------------------------------------ CRUD
    def get(self, obj_id: int):
        return self.session.get(self.model, obj_id)

    def list(self, **filters):
        stmt = select(self.model)
        for key, value in filters.items():
            stmt = stmt.where(getattr(self.model, key) == value)
        return list(self.session.scalars(stmt))

    def add(self, obj):
        self.session.add(obj)
        self.session.flush()
        self._touch_db()
        self._audit("CREATE", obj)
        return obj

    def update(self, obj, **fields):
        for key, value in fields.items():
            setattr(obj, key, value)
        self.session.flush()
        self._touch_db()
        self._audit("UPDATE", obj)
        return obj

    def delete(self, obj, force: bool = False) -> None:
        deps = self.dependencies(obj)
        if deps and not force:
            raise DependencyError(
                f"{self.entity_name} tem dependências; eliminação bloqueada.", deps
            )
        if deps and force:
            self._cascade(obj)
            self._audit("FORCE_DELETE", obj, detail="; ".join(deps))
        else:
            self._audit("DELETE", obj)
        self.session.delete(obj)
        self.session.flush()
        self._touch_db()

    # ------------------------------------------------- pontos de extensão
    def dependencies(self, obj) -> list[str]:
        """Lista humana de dependências que bloqueiam a eliminação."""
        return []

    def _cascade(self, obj) -> None:
        """Cascata executada apenas no force-delete."""

    # ------------------------------------------------------------ internos
    def _touch_db(self) -> None:
        set_meta(
            self.session,
            "db_last_modified",
            datetime.now().isoformat(timespec="seconds"),
        )

    def _audit(self, action: str, obj, detail: str = "") -> None:
        if self.audit is None:
            return
        label = (
            getattr(obj, "hostname", None)
            or getattr(obj, "name", None)
            or getattr(obj, "username", None)
            or ""
        )
        self.audit.log(
            action,
            entity=self.entity_name,
            entity_id=getattr(obj, "id", None),
            detail=f"{label} {detail}".strip(),
        )
