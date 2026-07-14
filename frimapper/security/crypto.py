"""Cifra de campos sensíveis em repouso (Fernet).

CRÍTICO: a chave ``secret.key`` deve viver SEPARADA da base de dados — quem
tiver os dois tem acesso aos campos cifrados (ver DEVLOG #008). O backup
normal é o export CSV, onde as credenciais nunca saem em claro.
"""

from __future__ import annotations

import os
from pathlib import Path

from cryptography.fernet import Fernet


class FieldCipher:
    def __init__(self, key: bytes) -> None:
        self._fernet = Fernet(key)

    @classmethod
    def load_or_create(cls, key_path: str | os.PathLike) -> "FieldCipher":
        """Carrega a chave do ficheiro; se não existir, gera-a (perms 0600)."""
        path = Path(key_path)
        if path.is_file():
            key = path.read_bytes().strip()
        else:
            key = Fernet.generate_key()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(key)
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass  # sistemas de ficheiros sem permissões POSIX (ex.: NTFS)
        return cls(key)

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")

    def decrypt(self, token: str) -> str:
        return self._fernet.decrypt(token.encode("ascii")).decode("utf-8")
