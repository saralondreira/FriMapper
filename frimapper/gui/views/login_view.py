"""Ecrã de login."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from ... import APP_NAME
from ..controllers.auth_controller import AuthController
from ..session import UserSession


class LoginView(QDialog):
    def __init__(self, auth: AuthController, first_run: bool = False, parent=None):
        super().__init__(parent)
        self.auth = auth
        self.session: UserSession | None = None
        self.setWindowTitle(f"{APP_NAME} — Login")
        self.setModal(True)

        layout = QVBoxLayout(self)
        title = QLabel(f"<h2>{APP_NAME}</h2>")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        if first_run:
            warning = QLabel(
                "Primeiro arranque: utilizador <b>master</b> / password "
                "<b>ChangeMe123!</b> — altere-a de imediato."
            )
            warning.setWordWrap(True)
            warning.setStyleSheet("color: #b35900;")
            layout.addWidget(warning)

        form = QFormLayout()
        self.username_edit = QLineEdit()
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        form.addRow("Utilizador:", self.username_edit)
        form.addRow("Password:", self.password_edit)
        layout.addLayout(form)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: red;")
        layout.addWidget(self.error_label)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._try_login)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _try_login(self) -> None:
        session = self.auth.login(
            self.username_edit.text().strip(), self.password_edit.text()
        )
        if session is None:
            self.error_label.setText("Credenciais inválidas ou conta inativa.")
            self.password_edit.clear()
            return
        self.session = session
        self.accept()
