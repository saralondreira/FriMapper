"""Janela principal do Frimapper.

Barra de pesquisa global; banners persistentes de mapa desatualizado
(vermelho) e de equipamentos órfãos (laranja); separadores: Equipamentos,
Localizações, Templates, Mapa e Utilizadores (este último só para Master).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from ... import APP_NAME, __version__
from ...repositories.base import DependencyError
from ...security.rbac import Permission
from ...services.bootstrap import AppContext
from ..controllers.auth_controller import AuthController
from ..controllers.device_controller import DeviceController
from ..controllers.export_controller import ExportController
from ..controllers.link_controller import LinkController
from ..controllers.location_controller import LocationController
from ..controllers.map_controller import MapController
from ..controllers.search_controller import SearchController
from ..controllers.template_controller import TemplateController
from ..controllers.user_controller import UserController
from ..models.device_table_model import DeviceTableModel
from ..session import UserSession
from .dialogs import (
    AdminPasswordDialog,
    DeviceAttributesDialog,
    DeviceDialog,
    LinkDialog,
    confirm_force_delete,
    show_orphan_alert,
)
from .node_synthesis_view import NodeSynthesisView
from .tabs import LocationsTab, TemplatesTab, UsersTab


class MapWorker(QThread):
    """Gera o mapa fora da thread da GUI.

    O contexto da ``diagrams`` é thread-local: TODO o trabalho (sessão de BD
    própria incluída) corre dentro de ``run()`` — ver DEVLOG #002.
    """

    done = Signal(str)
    failed = Signal(str)

    def __init__(self, controller: MapController, view: str,
                 location_id: int | None, parent=None):
        super().__init__(parent)
        self._controller = controller
        self._view = view
        self._location_id = location_id

    def run(self) -> None:
        try:
            self.done.emit(self._controller.generate(self._view, self._location_id))
        except Exception as exc:
            self.failed.emit(str(exc))


class DevicesTab(QWidget):
    """Separador de equipamentos (QTableView + DeviceTableModel com masking)."""

    def __init__(
        self,
        devices: DeviceController,
        links: LinkController,
        exports: ExportController,
        session: UserSession,
        auth: AuthController,
        on_change,
        parent=None,
    ):
        super().__init__(parent)
        self.devices = devices
        self.links = links
        self.exports = exports
        self.session = session
        self.auth = auth
        self.on_change = on_change

        layout = QVBoxLayout(self)
        self.model = DeviceTableModel(session)
        self.view = QTableView()
        self.view.setModel(self.model)
        self.view.setSelectionBehavior(QTableView.SelectRows)
        self.view.setSelectionMode(QTableView.SingleSelection)
        self.view.doubleClicked.connect(self._show_synthesis)
        self.view.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.view)

        buttons = QHBoxLayout()
        self.add_button = QPushButton("Adicionar")
        self.edit_button = QPushButton("Editar")
        self.delete_button = QPushButton("Eliminar")
        self.link_button = QPushButton("Ligar…")
        self.fields_button = QPushButton("Campos…")
        self.export_button = QPushButton("Exportar CSV")
        self.add_button.clicked.connect(self._add)
        self.edit_button.clicked.connect(self._edit)
        self.delete_button.clicked.connect(self._delete)
        self.link_button.clicked.connect(self._link)
        self.fields_button.clicked.connect(self._fields)
        self.export_button.clicked.connect(self._export)
        for button in (
            self.add_button,
            self.edit_button,
            self.delete_button,
            self.link_button,
            self.fields_button,
            self.export_button,
        ):
            buttons.addWidget(button)
        buttons.addStretch()
        layout.addLayout(buttons)

        self.add_button.setEnabled(session.can(Permission.CREATE))
        self.edit_button.setEnabled(session.can(Permission.EDIT))
        self.delete_button.setEnabled(session.can(Permission.DELETE))
        self.link_button.setEnabled(session.can(Permission.CREATE))
        self.fields_button.setEnabled(session.can(Permission.EDIT))
        self.export_button.setEnabled(session.can(Permission.EXPORT))

        self.refresh()

    def refresh(self) -> None:
        self.model.set_rows(self.devices.list_devices())

    def selected_id(self) -> int | None:
        indexes = self.view.selectionModel().selectedRows()
        return self.model.row_id(indexes[0].row()) if indexes else None

    def _changed(self) -> None:
        self.refresh()
        self.on_change()

    def _add(self) -> None:
        dialog = DeviceDialog(
            self.devices.template_options(), self.devices.location_options()
        )
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            self.devices.create(dialog.form())
            self._changed()
        except Exception as exc:
            QMessageBox.warning(self, "Erro", str(exc))

    def _edit(self) -> None:
        device_id = self.selected_id()
        if device_id is None:
            return
        dialog = DeviceDialog(
            self.devices.template_options(),
            self.devices.location_options(),
            self.devices.get_form(device_id),
        )
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            self.devices.update(device_id, dialog.form())
            self._changed()
        except Exception as exc:
            QMessageBox.warning(self, "Erro", str(exc))

    def _delete(self) -> None:
        device_id = self.selected_id()
        if device_id is None:
            return
        answer = QMessageBox.question(
            self,
            "Eliminar",
            "Eliminar este equipamento?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            self.devices.delete(device_id, force=False)
            self._changed()
            return
        except DependencyError as exc:
            dependencies = exc.dependencies
        except Exception as exc:
            QMessageBox.warning(self, "Erro", str(exc))
            return
        if not self.session.can(Permission.FORCE_DELETE):
            QMessageBox.warning(
                self,
                "Eliminação bloqueada",
                "Existem portas ligadas e o seu perfil não permite forçar:\n"
                + "\n".join(f"  • {d}" for d in dependencies[:15]),
            )
            return
        if not confirm_force_delete(self, dependencies):
            return
        if not AdminPasswordDialog.verify(self, self.auth):
            return
        orphans = self.devices.delete(device_id, force=True)
        show_orphan_alert(self, orphans)
        self._changed()

    def _link(self) -> None:
        devices, free_ports = self.links.form_data()
        if len(devices) < 2:
            QMessageBox.information(
                self, "Sem portas livres",
                "São precisos pelo menos dois equipamentos com portas livres.",
            )
            return
        dialog = LinkDialog(devices, free_ports)
        if dialog.exec() != QDialog.Accepted:
            return
        port_a, port_b, down = dialog.selected()
        if port_a is None or port_b is None:
            return
        try:
            self.links.create(port_a, port_b, down=down)
            self._changed()
        except Exception as exc:
            QMessageBox.warning(self, "Erro", str(exc))

    def _fields(self) -> None:
        device_id = self.selected_id()
        if device_id is None:
            return
        indexes = self.view.selectionModel().selectedRows()
        hostname = self.model.row_hostname(indexes[0].row())
        dialog = DeviceAttributesDialog(
            hostname, self.devices.get_attributes(device_id)
        )
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            self.devices.save_attributes(device_id, dialog.pairs())
            self._changed()
        except Exception as exc:
            QMessageBox.warning(self, "Erro", str(exc))

    def _export(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Pasta de destino")
        if not directory:
            return
        try:
            files = self.exports.export_csv(directory)
        except Exception as exc:
            QMessageBox.warning(self, "Erro", str(exc))
            return
        message = f"{len(files)} ficheiros CSV exportados."
        if self.exports.sharepoint_enabled():
            answer = QMessageBox.question(
                self, "SharePoint",
                message + "\n\nPublicar também no SharePoint?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer == QMessageBox.Yes:
                try:
                    self.exports.upload_to_sharepoint(files)
                    message += "\nPublicados no SharePoint."
                except Exception as exc:
                    QMessageBox.warning(self, "SharePoint", str(exc))
        QMessageBox.information(self, "Exportação", message)

    def _show_synthesis(self, index) -> None:
        device_id = self.model.row_id(index.row())
        NodeSynthesisView(self.devices.synthesis(device_id), self.session, self).exec()


class MapTab(QWidget):
    """Geração diferida do mapa (worker thread) + pré-visualização."""

    def __init__(self, maps: MapController, devices: DeviceController,
                 session: UserSession, parent=None):
        super().__init__(parent)
        self.maps = maps
        self.devices = devices
        self.session = session
        self._worker: MapWorker | None = None

        layout = QVBoxLayout(self)
        controls = QHBoxLayout()
        self.view_combo = QComboBox()
        self.view_combo.addItem("Rede completa", "full")
        self.view_combo.addItem("Core / Backbone", "core")
        self.view_combo.addItem("Por localização", "location")
        self.location_combo = QComboBox()
        self._reload_locations()
        self.location_combo.setEnabled(False)
        self.view_combo.currentIndexChanged.connect(
            lambda _: self.location_combo.setEnabled(
                self.view_combo.currentData() == "location"
            )
        )
        self.generate_button = QPushButton("Gerar Mapa")
        self.generate_button.setEnabled(session.can(Permission.GENERATE_MAP))
        self.generate_button.clicked.connect(self._generate)
        controls.addWidget(QLabel("Vista:"))
        controls.addWidget(self.view_combo)
        controls.addWidget(self.location_combo)
        controls.addWidget(self.generate_button)
        controls.addStretch()
        layout.addLayout(controls)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        self.preview_label = QLabel("Sem mapa gerado nesta sessão.")
        self.preview_label.setAlignment(Qt.AlignCenter)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.preview_label)
        layout.addWidget(scroll)

        last = self.maps.last_path()
        if last:
            self._show_png(last)

    def _reload_locations(self) -> None:
        self.location_combo.clear()
        for option in self.devices.location_options():
            if option.id is not None:
                self.location_combo.addItem(option.label, option.id)

    def refresh(self) -> None:
        self._reload_locations()

    def _generate(self) -> None:
        view = self.view_combo.currentData()
        location_id = (
            self.location_combo.currentData() if view == "location" else None
        )
        if view == "location" and location_id is None:
            QMessageBox.information(self, "Mapa", "Crie primeiro uma localização.")
            return
        self.generate_button.setEnabled(False)
        self.status_label.setText("A gerar o mapa…")
        self._worker = MapWorker(self.maps, view, location_id, self)
        self._worker.done.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(
            lambda: self.generate_button.setEnabled(True)
        )
        self._worker.start()

    def _on_done(self, path: str) -> None:
        self.status_label.setText(f"Mapa gerado: {path}")
        self._show_png(path)
        window = self.window()
        if hasattr(window, "refresh_banners"):
            window.refresh_banners()

    def _on_failed(self, message: str) -> None:
        self.status_label.setText("")
        QMessageBox.warning(self, "Geração do mapa", message)

    def _show_png(self, path: str) -> None:
        pixmap = QPixmap(path)
        if pixmap.isNull():
            self.preview_label.setText(f"Último mapa: {path}")
        else:
            self.preview_label.setPixmap(
                pixmap.scaledToWidth(1000, Qt.SmoothTransformation)
                if pixmap.width() > 1000
                else pixmap
            )


class SearchResultsDialog(QDialog):
    def __init__(self, term: str, hits, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Pesquisa — '{term}' ({len(hits)} resultados)")
        self.resize(720, 360)
        layout = QVBoxLayout(self)
        table = QTableWidget(len(hits), 6)
        table.setHorizontalHeaderLabels(
            ["Hostname", "Categoria", "Localização", "Campo", "Valor", "Ligado a"]
        )
        table.horizontalHeader().setStretchLastSection(True)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        for row, hit in enumerate(hits):
            for col, value in enumerate(
                [
                    hit.hostname,
                    hit.category,
                    hit.location,
                    hit.matched_field,
                    hit.matched_value,
                    hit.connected_to or "—",
                ]
            ):
                table.setItem(row, col, QTableWidgetItem(str(value)))
        layout.addWidget(table)


class MainWindow(QMainWindow):
    def __init__(self, ctx: AppContext, session: UserSession):
        super().__init__()
        self.ctx = ctx
        self.session = session
        self.setWindowTitle(
            f"{APP_NAME} v{__version__} — {session.username} ({session.role.label})"
        )
        self.resize(1100, 700)

        self.auth = AuthController(ctx)
        self.devices = DeviceController(ctx, session)
        self.links = LinkController(ctx, session)
        self.locations = LocationController(ctx, session)
        self.templates = TemplateController(ctx, session)
        self.maps = MapController(ctx, session)
        self.searches = SearchController(ctx, session)
        self.exports = ExportController(ctx, session)

        central = QWidget()
        layout = QVBoxLayout(central)

        # ---------------------------------------------------- pesquisa
        search_bar = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(
            "Pesquisar MAC, IP, utilizador, hostname, nº de série ou campo dinâmico…"
        )
        self.search_edit.returnPressed.connect(self._search)
        search_button = QPushButton("Pesquisar")
        search_button.clicked.connect(self._search)
        search_bar.addWidget(self.search_edit)
        search_bar.addWidget(search_button)
        layout.addLayout(search_bar)

        # ------------------------------------------------------ banners
        self.stale_banner = QLabel(
            "⚠  O mapa da rede encontra-se desatualizado — gere um novo mapa."
        )
        self.stale_banner.setStyleSheet(
            "background: #c62828; color: white; padding: 6px; border-radius: 3px;"
        )
        self.orphan_banner = QLabel("")
        self.orphan_banner.setStyleSheet(
            "background: #ef6c00; color: white; padding: 6px; border-radius: 3px;"
        )
        self.orphan_banner.setWordWrap(True)
        layout.addWidget(self.stale_banner)
        layout.addWidget(self.orphan_banner)

        # --------------------------------------------------- separadores
        self.tabs = QTabWidget()
        self.devices_tab = DevicesTab(
            self.devices,
            self.links,
            self.exports,
            session,
            self.auth,
            self.refresh_banners,
        )
        self.locations_tab = LocationsTab(
            self.locations, session, self.auth, self._structure_changed
        )
        self.templates_tab = TemplatesTab(
            self.templates, session, self.auth, self._structure_changed
        )
        self.map_tab = MapTab(self.maps, self.devices, session)
        self.tabs.addTab(self.devices_tab, "Equipamentos")
        self.tabs.addTab(self.locations_tab, "Localizações")
        self.tabs.addTab(self.templates_tab, "Templates")
        self.tabs.addTab(self.map_tab, "Mapa")
        self.users_tab = None
        if session.can(Permission.MANAGE_USERS):
            self.users_tab = UsersTab(
                UserController(ctx, session), session, self.auth, lambda: None
            )
            self.tabs.addTab(self.users_tab, "Utilizadores")
        layout.addWidget(self.tabs)

        self.setCentralWidget(central)
        self.refresh_banners()

    # ------------------------------------------------------------ ações
    def refresh_banners(self) -> None:
        self.stale_banner.setVisible(self.maps.is_stale())
        orphans = self.devices.orphan_hostnames()
        if orphans:
            self.orphan_banner.setText(
                "⚠  Equipamentos sem ligação (órfãos): "
                + ", ".join(orphans)
                + " — reponha as ligações com o botão 'Ligar…'."
            )
        self.orphan_banner.setVisible(bool(orphans))

    def _structure_changed(self) -> None:
        """Zonas/templates mudaram: atualizar equipamentos, mapa e banners."""
        self.devices_tab.refresh()
        self.map_tab.refresh()
        self.refresh_banners()

    def _search(self) -> None:
        term = self.search_edit.text().strip()
        if not term:
            return
        hits = self.searches.search(term)
        if not hits:
            QMessageBox.information(self, "Pesquisa", f"Sem resultados para '{term}'.")
            return
        SearchResultsDialog(term, hits, self).exec()
