"""Separação entre recursos read-only e dados graváveis.

Num executável PyInstaller os recursos vivem em ``sys._MEIPASS`` (pasta
temporária, read-only); os dados da aplicação (base de dados, chave de cifra,
logs de auditoria, mapas gerados) têm de viver numa pasta gravável e
persistente do utilizador. Este módulo é a única fonte de verdade para esses
dois caminhos.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from . import APP_NAME


def is_frozen() -> bool:
    """True quando a aplicação corre empacotada pelo PyInstaller."""
    return bool(getattr(sys, "frozen", False))


def resource_dir() -> Path:
    """Raiz dos recursos read-only (ícones, dados da diagrams, Graphviz)."""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def data_dir() -> Path:
    """Pasta gravável para BD, chave, logs e mapas (criada se necessário).

    Ordem: env var ``FRIMAPPER_DATA`` → ``%APPDATA%\\Frimapper`` (Windows) →
    ``~/.frimapper`` (restantes plataformas).
    """
    override = os.environ.get("FRIMAPPER_DATA")
    if override:
        base = Path(override)
    elif os.name == "nt":
        appdata = os.environ.get("APPDATA", str(Path.home()))
        base = Path(appdata) / APP_NAME
    else:
        base = Path.home() / ".frimapper"
    base.mkdir(parents=True, exist_ok=True)
    return base
