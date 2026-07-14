"""Tipos de coluna personalizados."""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.types import TypeDecorator


class EncryptedString(TypeDecorator):
    """Coluna de texto cifrada em repouso (Fernet).

    A cifra é injetada por ``set_cipher()`` durante o bootstrap, ANTES de
    qualquer acesso às colunas que usam este tipo (ver
    ``services/bootstrap.initialize_app`` e DEVLOG #004). Valores vazios/None
    passam sem cifrar para manter a semântica de "sem valor".
    """

    impl = String
    cache_ok = True

    _cipher = None

    @classmethod
    def set_cipher(cls, cipher) -> None:
        cls._cipher = cipher

    def process_bind_param(self, value, dialect):
        if value is None or value == "":
            return value
        if self._cipher is None:
            raise RuntimeError(
                "EncryptedString usado antes de set_cipher(); "
                "o bootstrap tem de configurar a cifra primeiro."
            )
        return self._cipher.encrypt(value)

    def process_result_value(self, value, dialect):
        if value is None or value == "":
            return value
        if self._cipher is None:
            raise RuntimeError(
                "EncryptedString usado antes de set_cipher(); "
                "o bootstrap tem de configurar a cifra primeiro."
            )
        return self._cipher.decrypt(value)
