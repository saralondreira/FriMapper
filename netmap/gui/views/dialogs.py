"""Diálogos CRUD e utilitários (force-delete, password de admin, campos…).

Todos os diálogos trabalham exclusivamente com DTOs (gui/dto.py).
"""

from __future__ import annotations

from datetime import date, datetime

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

from ...domain.enums import DeviceCategory, DeviceStatus, MaintenanceStatus, Role
from ..controllers.auth_controller import AuthController
from ..dto import (
    DeviceForm,
    LocationForm,
    MaintenanceForm,
    Option,
    PortForm,
    TemplateForm,
    UserForm,
    VlanForm,
)

#: Sugestões de campos dinâmicos comuns (DEVLOG #015).
COMMON_ATTRIBUTES = [
    "Detentor",
    "Conta logada",
    "IP secundário",
    "MAC secundário",
    "CPU",
    "RAM",
    "Disco",
    "Garantia até",
    "Contrato de suporte",
]


def _fill_combo(combo: QComboBox, options: list[Option], selected_id) -> None:
    combo.clear()
    for option in options:
        combo.addItem(option.label, option.id)
    for i in range(combo.count()):
        if combo.itemData(i) == selected_id:
            combo.setCurrentIndex(i)
            break


class DeviceDialog(QDialog):
    """Criação/edição de equipamento. Na criação, escolher um modelo herda
    as portas; na edição o modelo não é alterável (as portas já existem)."""

    def __init__(
        self,
        templates: list[Option],
        locations: list[Option],
        form: DeviceForm | None = None,
        vlan_options: list[str] | None = None,
        fixed_category: str | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.is_edit = form is not None
        form = form or DeviceForm(category=fixed_category or "computador")
        self.setWindowTitle("Editar equipamento" if self.is_edit else "Novo equipamento")

        layout = QFormLayout(self)
        self.hostname_edit = QLineEdit(form.hostname)
        layout.addRow("Hostname*:", self.hostname_edit)

        self.template_combo = QComboBox()
        _fill_combo(self.template_combo, templates, form.template_id)
        self.template_combo.setEnabled(not self.is_edit)
        layout.addRow("Modelo (herda portas):", self.template_combo)

        self.category_combo = QComboBox()
        for cat in DeviceCategory:
            self.category_combo.addItem(cat.value, cat.value)
        self.category_combo.setCurrentText(form.category)
        if fixed_category is not None:
            # Janela dedicada (ex.: firewalls): a categoria fica trancada.
            self.category_combo.setCurrentText(fixed_category)
            self.category_combo.setEnabled(False)
        layout.addRow("Categoria:", self.category_combo)

        self.location_combo = QComboBox()
        _fill_combo(self.location_combo, locations, form.location_id)
        layout.addRow("Localização:", self.location_combo)

        self.status_combo = QComboBox()
        for status in DeviceStatus:
            self.status_combo.addItem(status.value, status.value)
        self.status_combo.setCurrentText(form.status)
        layout.addRow("Estado:", self.status_combo)

        self.ip_edit = QLineEdit(form.ip_mgmt)
        self.mac_edit = QLineEdit(form.mac)
        self.vlan_combo = QComboBox()
        self.vlan_combo.setEditable(True)
        self.vlan_combo.addItem("")
        for vlan_label in vlan_options or []:
            self.vlan_combo.addItem(vlan_label)
        self.vlan_combo.setCurrentText(form.vlan)
        self.os_edit = QLineEdit(form.os_detected)
        self.user_edit = QLineEdit(form.assigned_user)
        self.serial_edit = QLineEdit(form.serial_number)
        layout.addRow("IP de gestão:", self.ip_edit)
        layout.addRow("MAC:", self.mac_edit)
        layout.addRow("VLAN (catálogo):", self.vlan_combo)
        layout.addRow("SO detetado:", self.os_edit)
        layout.addRow("Utilizador:", self.user_edit)
        layout.addRow("Nº de série:", self.serial_edit)

        self.snmp_edit = QLineEdit(form.snmp_community)
        self.snmp_edit.setEchoMode(QLineEdit.Password)
        self.access_edit = QLineEdit(form.access_password)
        self.access_edit.setEchoMode(QLineEdit.Password)
        layout.addRow("SNMP community 🔒:", self.snmp_edit)
        layout.addRow("Password de acesso 🔒:", self.access_edit)

        self.notes_edit = QTextEdit(form.notes)
        self.notes_edit.setMaximumHeight(60)
        layout.addRow("Notas:", self.notes_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def form(self) -> DeviceForm:
        return DeviceForm(
            hostname=self.hostname_edit.text().strip(),
            category=self.category_combo.currentData() or self.category_combo.currentText(),
            template_id=self.template_combo.currentData(),
            location_id=self.location_combo.currentData(),
            status=self.status_combo.currentData() or self.status_combo.currentText(),
            ip_mgmt=self.ip_edit.text().strip(),
            mac=self.mac_edit.text().strip(),
            vlan=self.vlan_combo.currentText().strip(),
            os_detected=self.os_edit.text().strip(),
            assigned_user=self.user_edit.text().strip(),
            serial_number=self.serial_edit.text().strip(),
            notes=self.notes_edit.toPlainText(),
            snmp_community=self.snmp_edit.text(),
            access_password=self.access_edit.text(),
        )


class LocationDialog(QDialog):
    def __init__(self, parents: list[Option], form: LocationForm | None = None, parent=None):
        super().__init__(parent)
        form = form or LocationForm()
        self.setWindowTitle("Zona/Localização")
        layout = QFormLayout(self)
        self.name_edit = QLineEdit(form.name)
        self.description_edit = QLineEdit(form.description)
        self.parent_combo = QComboBox()
        _fill_combo(self.parent_combo, parents, form.parent_id)
        layout.addRow("Nome*:", self.name_edit)
        layout.addRow("Descrição:", self.description_edit)
        layout.addRow("Zona-pai:", self.parent_combo)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def form(self) -> LocationForm:
        return LocationForm(
            name=self.name_edit.text().strip(),
            description=self.description_edit.text().strip(),
            parent_id=self.parent_combo.currentData(),
        )


class TemplateDialog(QDialog):
    def __init__(self, form: TemplateForm | None = None, parent=None):
        super().__init__(parent)
        form = form or TemplateForm()
        self.setWindowTitle("Modelo de equipamento")
        layout = QFormLayout(self)
        self.name_edit = QLineEdit(form.name)
        self.manufacturer_edit = QLineEdit(form.manufacturer)
        self.model_edit = QLineEdit(form.model)
        self.category_combo = QComboBox()
        for cat in DeviceCategory:
            self.category_combo.addItem(cat.value, cat.value)
        self.category_combo.setCurrentText(form.category)
        self.port_count_spin = QSpinBox()
        self.port_count_spin.setRange(0, 1024)
        self.port_count_spin.setValue(form.port_count)
        self.port_speeds_edit = QLineEdit(form.port_speeds)
        self.port_prefix_edit = QLineEdit(form.port_prefix)
        self.passive_check = QCheckBox("Equipamento passivo (régua/patch panel)")
        self.passive_check.setChecked(form.is_passive)
        layout.addRow("Nome*:", self.name_edit)
        layout.addRow("Fabricante:", self.manufacturer_edit)
        layout.addRow("Modelo:", self.model_edit)
        layout.addRow("Categoria:", self.category_combo)
        layout.addRow("Nº de portas:", self.port_count_spin)
        layout.addRow("Velocidades (ex. 1G,10G):", self.port_speeds_edit)
        layout.addRow("Prefixo das portas:", self.port_prefix_edit)
        layout.addRow("", self.passive_check)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def form(self) -> TemplateForm:
        return TemplateForm(
            name=self.name_edit.text().strip(),
            manufacturer=self.manufacturer_edit.text().strip(),
            model=self.model_edit.text().strip(),
            category=self.category_combo.currentData() or self.category_combo.currentText(),
            port_count=self.port_count_spin.value(),
            port_speeds=self.port_speeds_edit.text().strip(),
            port_prefix=self.port_prefix_edit.text().strip() or "Port",
            is_passive=self.passive_check.isChecked(),
        )


class UserDialog(QDialog):
    def __init__(self, form: UserForm | None = None, parent=None):
        super().__init__(parent)
        self.is_edit = form is not None
        form = form or UserForm()
        self.setWindowTitle("Utilizador")
        layout = QFormLayout(self)
        self.username_edit = QLineEdit(form.username)
        self.username_edit.setEnabled(not self.is_edit)
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        if self.is_edit:
            self.password_edit.setPlaceholderText("(vazio = manter a atual)")
        self.full_name_edit = QLineEdit(form.full_name)
        self.role_combo = QComboBox()
        for role in Role:
            self.role_combo.addItem(role.label, role.value)
        for i in range(self.role_combo.count()):
            if self.role_combo.itemData(i) == form.role:
                self.role_combo.setCurrentIndex(i)
        self.active_check = QCheckBox("Conta ativa")
        self.active_check.setChecked(form.is_active)
        layout.addRow("Utilizador*:", self.username_edit)
        layout.addRow("Password:", self.password_edit)
        layout.addRow("Nome completo:", self.full_name_edit)
        layout.addRow("Perfil:", self.role_combo)
        layout.addRow("", self.active_check)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def form(self) -> UserForm:
        return UserForm(
            username=self.username_edit.text().strip(),
            password=self.password_edit.text(),
            full_name=self.full_name_edit.text().strip(),
            role=self.role_combo.currentData(),
            is_active=self.active_check.isChecked(),
        )


class LinkDialog(QDialog):
    """Nova ligação — os dropdowns mostram APENAS portas livres."""

    def __init__(
        self,
        devices: list[Option],
        free_ports: dict[int, list[Option]],
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Nova ligação")
        self._free_ports = free_ports
        layout = QFormLayout(self)

        self.device_a_combo = QComboBox()
        self.port_a_combo = QComboBox()
        self.device_b_combo = QComboBox()
        self.port_b_combo = QComboBox()
        for combo in (self.device_a_combo, self.device_b_combo):
            for device in devices:
                combo.addItem(device.label, device.id)
        self.device_a_combo.currentIndexChanged.connect(
            lambda _: self._reload_ports(self.device_a_combo, self.port_a_combo)
        )
        self.device_b_combo.currentIndexChanged.connect(
            lambda _: self._reload_ports(self.device_b_combo, self.port_b_combo)
        )
        self._reload_ports(self.device_a_combo, self.port_a_combo)
        self._reload_ports(self.device_b_combo, self.port_b_combo)

        self.down_check = QCheckBox("Ligação em baixo (down)")

        layout.addRow("Equipamento A:", self.device_a_combo)
        layout.addRow("Porta A (livres):", self.port_a_combo)
        layout.addRow("Equipamento B:", self.device_b_combo)
        layout.addRow("Porta B (livres):", self.port_b_combo)
        layout.addRow("", self.down_check)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _reload_ports(self, device_combo: QComboBox, port_combo: QComboBox) -> None:
        port_combo.clear()
        device_id = device_combo.currentData()
        for port in self._free_ports.get(device_id, []):
            port_combo.addItem(port.label, port.id)

    def selected(self) -> tuple[int | None, int | None, bool]:
        return (
            self.port_a_combo.currentData(),
            self.port_b_combo.currentData(),
            self.down_check.isChecked(),
        )


class DeviceAttributesDialog(QDialog):
    """Campos dinâmicos (chave-valor) de um equipamento — DEVLOG #015."""

    def __init__(self, hostname: str, pairs: list[tuple[str, str]], parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Campos dinâmicos — {hostname}")
        self.resize(480, 360)
        layout = QVBoxLayout(self)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Campo", "Valor"])
        self.table.horizontalHeader().setStretchLastSection(True)
        for name, value in pairs:
            self._append_row(name, value)
        layout.addWidget(self.table)

        toolbar = QHBoxLayout()
        self.suggestion_combo = QComboBox()
        self.suggestion_combo.setEditable(True)
        self.suggestion_combo.addItems(COMMON_ATTRIBUTES)
        add_button = QPushButton("Adicionar campo")
        add_button.clicked.connect(
            lambda: self._append_row(self.suggestion_combo.currentText().strip(), "")
        )
        remove_button = QPushButton("Remover selecionado")
        remove_button.clicked.connect(
            lambda: self.table.removeRow(self.table.currentRow())
        )
        toolbar.addWidget(self.suggestion_combo)
        toolbar.addWidget(add_button)
        toolbar.addWidget(remove_button)
        layout.addLayout(toolbar)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _append_row(self, name: str, value: str) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(name))
        self.table.setItem(row, 1, QTableWidgetItem(value))

    def pairs(self) -> list[tuple[str, str]]:
        result = []
        for row in range(self.table.rowCount()):
            name_item = self.table.item(row, 0)
            value_item = self.table.item(row, 1)
            name = name_item.text().strip() if name_item else ""
            value = value_item.text() if value_item else ""
            if name:
                result.append((name, value))
        return result


class VlanDialog(QDialog):
    """Criação/edição de uma VLAN do catálogo."""

    def __init__(self, form: VlanForm | None = None, parent=None):
        super().__init__(parent)
        form = form or VlanForm()
        self.setWindowTitle("VLAN")
        layout = QFormLayout(self)
        self.vlan_id_spin = QSpinBox()
        self.vlan_id_spin.setRange(1, 4094)
        self.vlan_id_spin.setValue(form.vlan_id)
        self.name_edit = QLineEdit(form.name)
        self.description_edit = QLineEdit(form.description)
        layout.addRow("VLAN ID* (1–4094):", self.vlan_id_spin)
        layout.addRow("Nome:", self.name_edit)
        layout.addRow("Descrição:", self.description_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def form(self) -> VlanForm:
        return VlanForm(
            vlan_id=self.vlan_id_spin.value(),
            name=self.name_edit.text().strip(),
            description=self.description_edit.text().strip(),
        )


class MaintenanceDialog(QDialog):
    """Registo de manutenção: equipamento, datas, estado, técnico, descrição."""

    def __init__(
        self,
        devices: list[Option],
        form: MaintenanceForm | None = None,
        parent=None,
    ):
        super().__init__(parent)
        form = form or MaintenanceForm(date=date.today().isoformat())
        self.setWindowTitle("Manutenção")
        layout = QFormLayout(self)

        self.device_combo = QComboBox()
        _fill_combo(self.device_combo, devices, form.device_id)
        layout.addRow("Equipamento*:", self.device_combo)

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.setDate(
            QDate.fromString(form.date, "yyyy-MM-dd") if form.date else QDate.currentDate()
        )
        layout.addRow("Data*:", self.date_edit)

        self.status_combo = QComboBox()
        for status in MaintenanceStatus:
            self.status_combo.addItem(status.label, status.value)
        for i in range(self.status_combo.count()):
            if self.status_combo.itemData(i) == form.status:
                self.status_combo.setCurrentIndex(i)
        layout.addRow("Estado:", self.status_combo)

        self.next_check = QCheckBox("Agendar próxima manutenção")
        self.next_due_edit = QDateEdit()
        self.next_due_edit.setCalendarPopup(True)
        self.next_due_edit.setDisplayFormat("yyyy-MM-dd")
        if form.next_due:
            self.next_check.setChecked(True)
            self.next_due_edit.setDate(QDate.fromString(form.next_due, "yyyy-MM-dd"))
        else:
            self.next_due_edit.setDate(QDate.currentDate().addMonths(6))
            self.next_due_edit.setEnabled(False)
        self.next_check.toggled.connect(self.next_due_edit.setEnabled)
        layout.addRow("", self.next_check)
        layout.addRow("Próxima data:", self.next_due_edit)

        self.technician_edit = QLineEdit(form.technician)
        layout.addRow("Técnico:", self.technician_edit)
        self.description_edit = QTextEdit(form.description)
        self.description_edit.setMaximumHeight(80)
        layout.addRow("Descrição:", self.description_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def form(self) -> MaintenanceForm:
        return MaintenanceForm(
            device_id=self.device_combo.currentData(),
            date=self.date_edit.date().toString("yyyy-MM-dd"),
            next_due=(
                self.next_due_edit.date().toString("yyyy-MM-dd")
                if self.next_check.isChecked()
                else ""
            ),
            status=self.status_combo.currentData(),
            technician=self.technician_edit.text().strip(),
            description=self.description_edit.toPlainText(),
        )


class PortDialog(QDialog):
    """Criação/edição de uma porta (o estado é derivado das ligações)."""

    def __init__(
        self,
        form: PortForm | None = None,
        vlan_options: list[str] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        form = form or PortForm()
        self.setWindowTitle("Porta")
        layout = QFormLayout(self)
        self.name_edit = QLineEdit(form.name)
        self.speed_edit = QLineEdit(form.speed)
        self.vlan_combo = QComboBox()
        self.vlan_combo.setEditable(True)
        self.vlan_combo.addItem("")
        for vlan_label in vlan_options or []:
            self.vlan_combo.addItem(vlan_label)
        self.vlan_combo.setCurrentText(form.vlan)
        self.uplink_check = QCheckBox("Uplink / interface WAN")
        self.uplink_check.setChecked(form.is_uplink)
        layout.addRow("Nome*:", self.name_edit)
        layout.addRow("Velocidade:", self.speed_edit)
        layout.addRow("VLAN (catálogo):", self.vlan_combo)
        layout.addRow("", self.uplink_check)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def form(self) -> PortForm:
        return PortForm(
            name=self.name_edit.text().strip(),
            speed=self.speed_edit.text().strip(),
            vlan=self.vlan_combo.currentText().strip(),
            is_uplink=self.uplink_check.isChecked(),
        )


class LinkEditDialog(QDialog):
    """Edição de uma ligação existente: estado (up/down) e notas."""

    def __init__(self, description: str, down: bool, notes: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Editar ligação")
        layout = QFormLayout(self)
        layout.addRow(QLabel(description))
        self.down_check = QCheckBox("Ligação em baixo (down)")
        self.down_check.setChecked(down)
        self.notes_edit = QLineEdit(notes)
        layout.addRow("", self.down_check)
        layout.addRow("Notas:", self.notes_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def values(self) -> tuple[bool, str]:
        return self.down_check.isChecked(), self.notes_edit.text()


class ExportDialog(QDialog):
    """Janela de exportação CSV, com data visível e filtro de manutenções.

    A data/hora da exportação é estampada no nome da pasta
    (``export_<timestamp>/``) e mostrada aqui antes de confirmar.
    """

    def __init__(self, exports, parent=None):
        super().__init__(parent)
        self.exports = exports
        self.exported_files: list[str] = []
        self.setWindowTitle("Exportar base de dados para CSV")
        layout = QFormLayout(self)

        self._timestamp = datetime.now()
        self.date_label = QLabel(
            f"<b>Data da exportação:</b> {self._timestamp:%Y-%m-%d %H:%M:%S}"
        )
        layout.addRow(self.date_label)
        self.folder_label = QLabel(
            f"Pasta a criar: export_{self._timestamp:%Y%m%d_%H%M%S}/ (8 CSV)"
        )
        layout.addRow(self.folder_label)

        dir_row = QHBoxLayout()
        self.dir_edit = QLineEdit()
        self.dir_edit.setPlaceholderText("Pasta de destino…")
        browse_button = QPushButton("Procurar…")
        browse_button.clicked.connect(self._browse)
        dir_row.addWidget(self.dir_edit)
        dir_row.addWidget(browse_button)
        layout.addRow("Destino*:", dir_row)

        self.since_check = QCheckBox("Exportar apenas manutenções desde:")
        self.since_edit = QDateEdit()
        self.since_edit.setCalendarPopup(True)
        self.since_edit.setDisplayFormat("yyyy-MM-dd")
        self.since_edit.setDate(QDate.currentDate().addYears(-1))
        self.since_edit.setEnabled(False)
        self.since_check.toggled.connect(self.since_edit.setEnabled)
        layout.addRow("", self.since_check)
        layout.addRow("Desde:", self.since_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Exportar")
        buttons.accepted.connect(self._do_export)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _browse(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Pasta de destino")
        if directory:
            self.dir_edit.setText(directory)

    def maintenance_since(self) -> date | None:
        if not self.since_check.isChecked():
            return None
        qdate = self.since_edit.date()
        return date(qdate.year(), qdate.month(), qdate.day())

    def _do_export(self) -> None:
        directory = self.dir_edit.text().strip()
        if not directory:
            QMessageBox.warning(self, "Exportação", "Escolha a pasta de destino.")
            return
        try:
            self.exported_files = self.exports.export_csv(
                directory, maintenance_since=self.maintenance_since()
            )
        except Exception as exc:
            QMessageBox.warning(self, "Exportação", str(exc))
            return
        message = f"{len(self.exported_files)} ficheiros CSV exportados."
        if self.exports.sharepoint_enabled():
            answer = QMessageBox.question(
                self, "SharePoint",
                message + "\n\nPublicar também no SharePoint?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer == QMessageBox.Yes:
                try:
                    self.exports.upload_to_sharepoint(self.exported_files)
                    message += "\nPublicados no SharePoint."
                except Exception as exc:
                    QMessageBox.warning(self, "SharePoint", str(exc))
        QMessageBox.information(self, "Exportação", message)
        self.accept()


class AdminPasswordDialog(QDialog):
    """Override por password de administrador (force-delete)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Autorização de Master")
        layout = QFormLayout(self)
        info = QLabel(
            "Esta eliminação força a remoção em cascata das dependências.\n"
            "Introduza credenciais de um utilizador Master para continuar."
        )
        layout.addRow(info)
        self.username_edit = QLineEdit("master")
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        layout.addRow("Utilizador Master:", self.username_edit)
        layout.addRow("Password:", self.password_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def credentials(self) -> tuple[str, str]:
        return self.username_edit.text().strip(), self.password_edit.text()

    @staticmethod
    def verify(parent, auth: AuthController) -> bool:
        dialog = AdminPasswordDialog(parent)
        while dialog.exec() == QDialog.Accepted:
            username, password = dialog.credentials()
            if auth.verify_admin(username, password):
                return True
            QMessageBox.warning(
                parent, "Autorização recusada",
                "Credenciais de Master inválidas.",
            )
        return False


def confirm_force_delete(parent, dependencies: list[str]) -> bool:
    """Mostra as dependências e pergunta se avança para o cascade."""
    listing = "\n".join(f"  • {dep}" for dep in dependencies[:15])
    if len(dependencies) > 15:
        listing += f"\n  … e mais {len(dependencies) - 15}"
    answer = QMessageBox.warning(
        parent,
        "Eliminação bloqueada",
        "Não é possível eliminar porque existem dependências:\n\n"
        f"{listing}\n\n"
        "Forçar a eliminação em cascata (requer password de Master)?",
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.No,
    )
    return answer == QMessageBox.Yes


def show_orphan_alert(parent, orphans: list[str]) -> None:
    """Alerta imediato de equipamentos que ficaram sem ligação."""
    if not orphans:
        return
    names = ", ".join(orphans)
    QMessageBox.warning(
        parent,
        "Equipamentos órfãos",
        "A eliminação deixou equipamentos SEM LIGAÇÃO:\n\n"
        f"  {names}\n\n"
        "Reponha as ligações com o botão 'Ligar…' no separador Equipamentos.",
    )
