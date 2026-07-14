"""Acesso à tabela ``system_meta`` (pares chave-valor de sistema)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..db.models import SystemMeta


def get_meta(session: Session, key: str, default: str = "") -> str:
    row = session.get(SystemMeta, key)
    return row.value if row is not None else default


def set_meta(session: Session, key: str, value: str) -> None:
    row = session.get(SystemMeta, key)
    if row is None:
        session.add(SystemMeta(key=key, value=value))
    else:
        row.value = value
    session.flush()
