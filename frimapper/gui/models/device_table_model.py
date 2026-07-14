"""QAbstractTableModel de equipamentos, ciente da sessão RBAC.

Aplica o data masking por campo (perfil MAINTENANCE vê ``***``) e destaca a
laranja as linhas de equipamentos órfãos (``needs_relink``).
"""

from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QBrush, QColor

from ...security.rbac import mask_value
from ..dto import DeviceRow
from ..session import UserSession

HEADERS = ["Hostname", "Categoria", "Localização", "IP", "MAC", "VLAN",
           "Utilizador", "Estado"]
FIELDS = ["hostname", "category", "location", "ip_mgmt", "mac", "vlan",
          "assigned_user", "status"]

_ORPHAN_BACKGROUND = QColor(255, 204, 128)  # laranja — pede reposição de ligação


class DeviceTableModel(QAbstractTableModel):
    def __init__(self, session: UserSession, parent=None) -> None:
        super().__init__(parent)
        self._session = session
        self._rows: list[DeviceRow] = []

    def set_rows(self, rows: list[DeviceRow]) -> None:
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()

    def row_id(self, row: int) -> int:
        return self._rows[row].id

    def row_hostname(self, row: int) -> str:
        return self._rows[row].hostname

    # ----------------------------------------------------- QAbstractTable
    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(HEADERS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return HEADERS[section]
        return None

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        if role == Qt.DisplayRole:
            field = FIELDS[index.column()]
            return mask_value(self._session.role, field, getattr(row, field))
        if role == Qt.BackgroundRole and row.needs_relink:
            return QBrush(_ORPHAN_BACKGROUND)
        if role == Qt.ToolTipRole and row.needs_relink:
            return "Equipamento órfão — reponha a ligação com o botão 'Ligar…'."
        return None
