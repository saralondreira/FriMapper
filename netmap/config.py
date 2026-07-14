"""Configuração da aplicação (``config.ini`` + variáveis de ambiente).

A connection string pode ser trocada para migrar de SQLite para
PostgreSQL/MySQL/SQL Server sem tocar em mais nada acima da camada ``db/``
(basta instalar o driver correspondente: psycopg / PyMySQL / pyodbc).

Env vars suportadas:
- ``NETMAP_DATABASE_URL``     — override da connection string
- ``NETMAP_SP_CLIENT_SECRET`` — segredo do conector SharePoint (nunca em ficheiro)
- ``FRIMAPPER_DATA``          — override da pasta de dados graváveis
"""

from __future__ import annotations

import configparser
import os
from dataclasses import dataclass, field
from pathlib import Path

from .paths import data_dir, resource_dir


@dataclass
class SharePointConfig:
    enabled: bool = False
    tenant_id: str = ""
    client_id: str = ""
    site: str = ""
    folder: str = ""


@dataclass
class AppConfig:
    database_url: str
    echo: bool
    audit_log: Path
    secret_key: Path
    map_output: Path
    icon_dir: Path
    graphviz_dot_path: str | None
    sharepoint: SharePointConfig = field(default_factory=SharePointConfig)

    @classmethod
    def load(cls, ini_path: str | os.PathLike | None = None) -> "AppConfig":
        data = data_dir()
        parser = configparser.ConfigParser()
        path = Path(ini_path) if ini_path else data / "config.ini"
        if path.is_file():
            parser.read(path, encoding="utf-8")

        default_db = f"sqlite:///{data / 'network_inventory.db'}"
        database_url = os.environ.get("NETMAP_DATABASE_URL") or parser.get(
            "database", "url", fallback=default_db
        )
        echo = parser.getboolean("database", "echo", fallback=False)

        audit_log = Path(
            parser.get("paths", "audit_log", fallback=str(data / "audit_network.log"))
        )
        secret_key = Path(
            parser.get("paths", "secret_key", fallback=str(data / "secret.key"))
        )
        map_output = Path(
            parser.get("paths", "map_output", fallback=str(data / "maps"))
        )
        icon_dir = Path(
            parser.get(
                "paths", "icon_dir", fallback=str(resource_dir() / "assets" / "icons")
            )
        )
        graphviz_dot_path = parser.get("paths", "graphviz_dot_path", fallback="") or None

        sharepoint = SharePointConfig(
            enabled=parser.getboolean("sharepoint", "enabled", fallback=False),
            tenant_id=parser.get("sharepoint", "tenant_id", fallback=""),
            client_id=parser.get("sharepoint", "client_id", fallback=""),
            site=parser.get("sharepoint", "site", fallback=""),
            folder=parser.get("sharepoint", "folder", fallback=""),
        )

        return cls(
            database_url=database_url,
            echo=echo,
            audit_log=audit_log,
            secret_key=secret_key,
            map_output=map_output,
            icon_dir=icon_dir,
            graphviz_dot_path=graphviz_dot_path,
            sharepoint=sharepoint,
        )
