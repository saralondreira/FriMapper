"""Bootstrap da aplicação.

Ordem de inicialização OBRIGATÓRIA (ver DEVLOG #004): carregar/criar a chave
Fernet → injetar a cifra em ``EncryptedString`` → só depois criar o engine e
o schema. Qualquer acesso a colunas cifradas antes disso levanta RuntimeError.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select

from .. import __version__
from ..config import AppConfig
from ..db.base import Database
from ..db.models import User
from ..db.types import EncryptedString
from ..domain.enums import Role
from ..runtime import configure_graphviz
from ..security.audit import AuditLogger
from ..security.auth import hash_password
from ..security.crypto import FieldCipher
from ..repositories.repositories import UserRepository

DEFAULT_MASTER_USERNAME = "master"
DEFAULT_MASTER_PASSWORD = "ChangeMe123!"


@dataclass
class AppContext:
    """Contexto partilhado por serviços e controllers."""

    config: AppConfig
    db: Database
    cipher: FieldCipher
    audit: AuditLogger


def initialize_app(config: AppConfig) -> AppContext:
    configure_graphviz(config.graphviz_dot_path)
    cipher = FieldCipher.load_or_create(config.secret_key)
    EncryptedString.set_cipher(cipher)  # antes de qualquer acesso às colunas cifradas
    db = Database(config.database_url, echo=config.echo)
    db.create_all()
    audit = AuditLogger(config.audit_log)
    audit.log("BOOTSTRAP", entity="app", detail=f"Frimapper v{__version__}")
    return AppContext(config=config, db=db, cipher=cipher, audit=audit)


def ensure_master_user(
    ctx: AppContext,
    username: str = DEFAULT_MASTER_USERNAME,
    password: str = DEFAULT_MASTER_PASSWORD,
) -> bool:
    """Cria o utilizador Master por defeito no primeiro arranque.

    Devolve True se o utilizador foi criado agora (a GUI usa isto para pedir
    a troca imediata da password por defeito).
    """
    with ctx.db.session() as session:
        total = session.scalar(select(func.count()).select_from(User))
        if total:
            return False
        repo = UserRepository(session, ctx.audit)
        repo.add(
            User(
                username=username,
                password_hash=hash_password(password),
                full_name="Administrador Master",
                role=Role.MASTER,
            )
        )
        return True
