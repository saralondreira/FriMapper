"""Janela de CRUD de portas de um equipamento.

Aberta a partir dos separadores Equipamentos e Firewalls (botão "Portas…").
Portas com ligação não são elimináveis aqui — a ligação remove-se primeiro
no separador Ligações (integridade estrita, sem atalhos).
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ...repositories.base import DependencyError
from ...security.rbac import Permission
from ..controllers.port_controller import PortController
from ..session import UserSession
from .dialogs import PortDialog


class PortsDialog(QDialog):
    COLUMNS = ["Porta", "Velocidade", "Estado", "VLAN", "Uplink/WAN", "Ligada a"]

    def __init__(
        self,
        ports: PortController,
        device_id: int,
        hostname: str,
        session: UserSession,
        vlan_options: list[str] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.ports = ports
        self.device_id = device_id
        self.vlan_options = vlan_options or []
        self.changed = False
        self.setWindowTitle(f"Portas — {hostname}")
        self.resize(640, 400)

        layout = QVBoxLayout(self)
        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)

        buttons = QHBoxLayout()
        self.new_button = QPushButton("Nova porta")
        self.edit_button = QPushButton("Editar")
        self.delete_button = QPushButton("Eliminar")
        self.new_button.clicked.connect(self._new)
        self.edit_button.clicked.connect(self._edit)
        self.delete_button.clicked.connect(self._delete)
        for button in (self.new_button, self.edit_button, self.delete_button):
            buttons.addWidget(button)
        buttons.addStretch()
        close_button = QPushButton("Fechar")
        close_button.clicked.connect(self.accept)
        buttons.addWidget(close_button)
        layout.addLayout(buttons)

        self.new_button.setEnabled(session.can(Permission.CREATE))
        self.edit_button.setEnabled(session.can(Permission.EDIT))
        self.delete_button.setEnabled(session.can(Permission.DELETE))

        self._ids: list[int] = []
        self.refresh()

    def refresh(self) -> None:
        rows = self.ports.list_rows(self.device_id)
        self._ids = [row.id for row in rows]
        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            values = [
                row.name,
                row.speed,
                row.status,
                row.vlan,
                "sim" if row.is_uplink else "",
                row.connected_to or "—",
            ]
            for col, value in enumerate(values):
                self.table.setItem(i, col, QTableWidgetItem(str(value)))

    def _selected_id(self) -> int | None:
        row = self.table.currentRow()
        return self._ids[row] if 0 <= row < len(self._ids) else None

    def _new(self) -> None:
        dialog = PortDialog(vlan_options=self.vlan_options, parent=self)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            self.ports.create(self.device_id, dialog.form())
            self.changed = True
            self.refresh()
        except Exception as exc:
            QMessageBox.warning(self, "Erro", str(exc))

    def _edit(self) -> None:
        port_id = self._selected_id()
        if port_id is None:
            return
        dialog = PortDialog(
            self.ports.get_form(port_id), vlan_options=self.vlan_options, parent=self
        )
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            self.ports.update(port_id, dialog.form())
            self.changed = True
            self.refresh()
        except Exception as exc:
            QMessageBox.warning(self, "Erro", str(exc))

    def _delete(self) -> None:
        port_id = self._selected_id()
        if port_id is None:
            return
        answer = QMessageBox.question(
            self, "Eliminar", "Eliminar esta porta?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            self.ports.delete(port_id)
            self.changed = True
            self.refresh()
        except DependencyError:
            QMessageBox.warning(
                self,
                "Porta ocupada",
                "Esta porta tem uma ligação. Elimine primeiro a ligação no "
                "separador 'Ligações'.",
            )
        except Exception as exc:
            QMessageBox.warning(self, "Erro", str(exc))
