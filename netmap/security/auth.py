"""Hashing de passwords (passlib, esquema primário argon2)."""

from __future__ import annotations

from passlib.context import CryptContext

_pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _pwd_context.verify(password, password_hash)
    except ValueError:
        return False


def needs_rehash(password_hash: str) -> bool:
    """True se o hash usa um esquema/parâmetros desatualizados.

    Verificado no login para fazer rehash transparente.
    """
    return _pwd_context.needs_update(password_hash)
