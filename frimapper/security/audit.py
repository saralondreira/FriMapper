"""Audit logging.

Formato de cada linha de ``audit_network.log``::

    data | host=<máquina> | user=<u> | action=<A> | entity=<E> | id=<id> | <detalhe>

Ações registadas: CREATE, UPDATE, DELETE, FORCE_DELETE, LOGIN_OK, LOGIN_FAIL,
BOOTSTRAP. Rotação automática: 5 MB × 10 ficheiros.
"""

from __future__ import annotations

import logging
import socket
from logging.handlers import RotatingFileHandler
from pathlib import Path


class AuditLogger:
    def __init__(self, log_path: str | Path) -> None:
        self.host = socket.gethostname()
        self.current_user = "-"
        path = Path(log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._logger = logging.getLogger(f"frimapper.audit.{id(self)}")
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False
        handler = RotatingFileHandler(
            path, maxBytes=5 * 1024 * 1024, backupCount=10, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))
        self._logger.addHandler(handler)

    def set_user(self, username: str | None) -> None:
        """Define o utilizador da sessão atual (após login)."""
        self.current_user = username or "-"

    def log(
        self,
        action: str,
        entity: str = "",
        entity_id: int | None = None,
        detail: str = "",
    ) -> None:
        self._logger.info(
            "host=%s | user=%s | action=%s | entity=%s | id=%s | %s",
            self.host,
            self.current_user,
            action,
            entity or "-",
            entity_id if entity_id is not None else "-",
            detail,
        )
