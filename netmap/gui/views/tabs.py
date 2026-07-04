"""Separadores CRUD da janela principal.

``CrudTab`` é a base genérica: tabela + Novo/Editar/Eliminar com RBAC e o
fluxo completo de force-delete (confirmação de dependências → password de
Master → cascade → alerta de órfãos). Os separadores concretos fornecem o
controller e a formatação das linhas.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...repositories.base import DependencyError
from ...security.rbac import Permission
from ..controllers.auth_controller import AuthController
from ..session import UserSession
from .dialogs import (
    AdminPasswordDialog,
    LocationDialog,
    TemplateDialog,
    UserDialog,
    confirm_force_delete,
    show_orphan_alert,
)


class CrudTab(QWidget):
    """Base genérica de separador CRUD (tabela + botões, ciente do RBAC)."""

    columns: list[str] = []
    entity_label = "registo"

    def __init__(
        self,
        session: UserSession,
        auth: AuthController,
        on_change=None,
        parent=None,
    ):
        super().__init__(parent)
        self.session = session
        self.auth = auth
        self.on_change = on_change or (lambda: None)
        self._ids: list[int] = []

        layout = QVBoxLayout(self)
        self.table = QTableWidget(0, len(self.columns))
        self.table.setHorizontalHeaderLabels(self.columns)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)

        buttons = QHBoxLayout()
        self.new_button = QPushButton("Novo")
        self.edit_button = QPushButton("Editar")
        self.delete_button = QPushButton("Eliminar")
        self.new_button.clicked.connect(self._new_clicked)
        self.edit_button.clicked.connect(self._edit_clicked)
        self.delete_button.clicked.connect(self._delete_clicked)
        for button in (self.new_button, self.edit_button, self.delete_button):
            buttons.addWidget(button)
        buttons.addStretch()
        layout.addLayout(buttons)

        # RBAC: Manutenção é só leitura.
        self.new_button.setEnabled(session.can(Permission.CREATE))
        self.edit_button.setEnabled(session.can(Permission.EDIT))
        self.delete_button.setEnabled(session.can(Permission.DELETE))

        self.refresh()

    # ---------------------------------------------------------- interface
    def load_rows(self) -> list[tuple[int, list[str]]]:
        raise NotImplementedError

    def create_flow(self) -> bool:
        raise NotImplementedError

    def edit_flow(self, entity_id: int) -> bool:
        raise NotImplementedError

    def delete_entity(self, entity_id: int, force: bool) -> list[str]:
        """Chama o controller; devolve hostnames órfãos (se force)."""
        raise NotImplementedError

    # ------------------------------------------------------------ comum
    def refresh(self) -> None:
        rows = self.load_rows()
        self._ids = [entity_id for entity_id, _ in rows]
        self.table.setRowCount(len(rows))
        for row, (_, values) in enumerate(rows):
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(str(value)))

    def selected_id(self) -> int | None:
        row = self.table.currentRow()
        return self._ids[row] if 0 <= row < len(self._ids) else None

    def _changed(self) -> None:
        self.refresh()
        self.on_change()

    def _new_clicked(self) -> None:
        try:
            if self.create_flow():
                self._changed()
        except Exception as exc:  # ValueError de validação, etc.
            QMessageBox.warning(self, "Erro", str(exc))

    def _edit_clicked(self) -> None:
        entity_id = self.selected_id()
        if entity_id is None:
            return
        try:
            if self.edit_flow(entity_id):
                self._changed()
        except Exception as exc:
            QMessageBox.warning(self, "Erro", str(exc))

    def _delete_clicked(self) -> None:
        entity_id = self.selected_id()
        if entity_id is None:
            return
        answer = QMessageBox.question(
            self,
            "Eliminar",
            f"Eliminar este {self.entity_label}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            self.delete_entity(entity_id, force=False)
            self._changed()
            return
        except DependencyError as exc:
            dependencies = exc.dependencies
        except Exception as exc:
            QMessageBox.warning(self, "Erro", str(exc))
            return

        # Fluxo de force-delete: dependências → password de Master → cascade.
        if not self.session.can(Permission.FORCE_DELETE):
            QMessageBox.warning(
                self,
                "Eliminação bloqueada",
                "Existem dependências e o seu perfil não permite forçar:\n"
                + "\n".join(f"  • {d}" for d in dependencies[:15]),
            )
            return
        if not confirm_force_delete(self, dependencies):
            return
        if not AdminPasswordDialog.verify(self, self.auth):
            return
        try:
            orphans = self.delete_entity(entity_id, force=True)
        except DependencyError as exc:
            QMessageBox.warning(self, "Eliminação recusada", str(exc))
            return
        show_orphan_alert(self, orphans)
        self._changed()


class LocationsTab(CrudTab):
    columns = ["Nome", "Descrição", "Zona-pai"]
    entity_label = "zona"

    def __init__(self, controller, session, auth, on_change=None, parent=None):
        self.controller = controller
        super().__init__(session, auth, on_change, parent)

    def load_rows(self):
        return [
            (row.id, [row.name, row.description, row.parent])
            for row in self.controller.list_rows()
        ]

    def create_flow(self) -> bool:
        dialog = LocationDialog(self.controller.options())
        if dialog.exec() != LocationDialog.Accepted:
            return False
        self.controller.create(dialog.form())
        return True

    def edit_flow(self, entity_id: int) -> bool:
        dialog = LocationDialog(
            self.controller.options(exclude_id=entity_id),
            self.controller.get_form(entity_id),
        )
        if dialog.exec() != LocationDialog.Accepted:
            return False
        self.controller.update(entity_id, dialog.form())
        return True

    def delete_entity(self, entity_id: int, force: bool) -> list[str]:
        return self.controller.delete(entity_id, force=force)


class TemplatesTab(CrudTab):
    columns = ["Nome", "Fabricante", "Modelo", "Categoria", "Portas"]
    entity_label = "modelo"

    def __init__(self, controller, session, auth, on_change=None, parent=None):
        self.controller = controller
        super().__init__(session, auth, on_change, parent)

    def load_rows(self):
        return [
            (
                row.id,
                [row.name, row.manufacturer, row.model, row.category, row.port_count],
            )
            for row in self.controller.list_rows()
        ]

    def create_flow(self) -> bool:
        dialog = TemplateDialog()
        if dialog.exec() != TemplateDialog.Accepted:
            return False
        self.controller.create(dialog.form())
        return True

    def edit_flow(self, entity_id: int) -> bool:
        dialog = TemplateDialog(self.controller.get_form(entity_id))
        if dialog.exec() != TemplateDialog.Accepted:
            return False
        self.controller.update(entity_id, dialog.form())
        return True

    def delete_entity(self, entity_id: int, force: bool) -> list[str]:
        return self.controller.delete(entity_id, force=force)


class UsersTab(CrudTab):
    columns = ["Utilizador", "Nome", "Perfil", "Ativo"]
    entity_label = "utilizador"

    def __init__(self, controller, session, auth, on_change=None, parent=None):
        self.controller = controller
        super().__init__(session, auth, on_change, parent)
        # Gestão de utilizadores é exclusiva do Master (MANAGE_USERS).
        allowed = session.can(Permission.MANAGE_USERS)
        self.new_button.setEnabled(allowed)
        self.edit_button.setEnabled(allowed)
        self.delete_button.setEnabled(allowed)

    def load_rows(self):
        return [
            (
                row.id,
                [
                    row.username,
                    row.full_name,
                    row.role,
                    "sim" if row.is_active else "não",
                ],
            )
            for row in self.controller.list_rows()
        ]

    def create_flow(self) -> bool:
        dialog = UserDialog()
        if dialog.exec() != UserDialog.Accepted:
            return False
        self.controller.create(dialog.form())
        return True

    def edit_flow(self, entity_id: int) -> bool:
        dialog = UserDialog(self.controller.get_form(entity_id))
        if dialog.exec() != UserDialog.Accepted:
            return False
        self.controller.update(entity_id, dialog.form())
        return True

    def delete_entity(self, entity_id: int, force: bool) -> list[str]:
        return self.controller.delete(entity_id, force=force)
