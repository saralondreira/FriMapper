"""Camada de acesso à base de dados.

Este módulo é o ÚNICO sítio que conhece o motor concreto. Migrar de SQLite
para PostgreSQL/MySQL/SQL Server exige apenas mudar a connection string em
``config.ini`` (e instalar o driver) — modelos, repositórios, serviços e GUI
não mudam.
"""

from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Base declarativa de todos os modelos ORM."""


class Database:
    """Encapsula engine + sessionmaker.

    No SQLite as foreign keys vêm DESLIGADAS por defeito; o listener abaixo
    executa ``PRAGMA foreign_keys=ON`` em cada ligação para repor a rede de
    segurança relacional (só é registado quando o motor é SQLite).
    """

    def __init__(self, url: str, echo: bool = False) -> None:
        self.engine = create_engine(url, echo=echo, future=True)
        if self.engine.dialect.name == "sqlite":

            @event.listens_for(self.engine, "connect")
            def _enable_sqlite_fk(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

        self.session_factory = sessionmaker(
            bind=self.engine, expire_on_commit=False, future=True
        )

    def create_all(self) -> None:
        from . import models  # noqa: F401 — regista as tabelas na metadata

        Base.metadata.create_all(self.engine)

    @contextmanager
    def session(self):
        """Unit of Work: os repositórios fazem flush, o commit acontece aqui."""
        session: Session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
