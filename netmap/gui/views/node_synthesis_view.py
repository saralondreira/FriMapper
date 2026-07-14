"""Painel de síntese por nó: portas, ligado-a, utilizador, VLAN e estado."""

from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ...security.rbac import mask_value
from ..dto import SynthesisView
from ..session import UserSession

_STATUS_COLORS = {
    "up": QColor(46, 125, 50),
    "down": QColor(198, 40, 40),
    "unused": QColor(117, 117, 117),
}


class NodeSynthesisView(QDialog):
    def __init__(self, synthesis: SynthesisView, session: UserSession, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Síntese — {synthesis.hostname}")
        self.resize(640, 420)
        layout = QVBoxLayout(self)

        header = QLabel(
            f"<b>{synthesis.hostname}</b> · {synthesis.category} · "
            f"{synthesis.location or 'sem localização'} · estado: {synthesis.status}"
            + (f" · modelo: {synthesis.template}" if synthesis.template else "")
        )
        header.setWordWrap(True)
        layout.addWidget(header)

        self.table = QTableWidget(len(synthesis.ports), 6)
        self.table.setHorizontalHeaderLabels(
            ["Porta", "Velocidade", "Estado", "VLAN", "Ligado a", "Utilizador"]
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        for row, port in enumerate(synthesis.ports):
            connected = (
                f"{port.connected_device}:{port.connected_port}"
                if port.connected_device
                else "—"
            )
            status_item = QTableWidgetItem(port.status)
            color = _STATUS_COLORS.get(port.status)
            if color is not None:
                status_item.setForeground(color)
            # A VLAN é campo sensível — mascarada para o perfil Manutenção.
            vlan = mask_value(session.role, "vlan", port.vlan) or ""
            for col, item in enumerate(
                [
                    QTableWidgetItem(port.name),
                    QTableWidgetItem(port.speed),
                    status_item,
                    QTableWidgetItem(vlan),
                    QTableWidgetItem(connected),
                    QTableWidgetItem(port.user),
                ]
            ):
                self.table.setItem(row, col, item)
        layout.addWidget(self.table)
