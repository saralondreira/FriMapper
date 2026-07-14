"""Testes de interação da GUI com QTest (offscreen) — 10 verificações.

Complementa o ``gui_smoke.py`` (que apenas constrói widgets): aqui os fluxos
são exercitados com cliques e teclado SIMULADOS (``QtTest.QTest``), cobrindo
a limitação assinalada no MANUAL §24. Fluxos modais (``exec()``) continuam
fora do âmbito — não há event loop bloqueante em CI.

Uso: ``QT_QPA_PLATFORM=offscreen python tests/gui_interaction.py``.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_tmp = tempfile.TemporaryDirectory(prefix="frimapper-gui-qtest-")
os.environ["FRIMAPPER_DATA"] = _tmp.name

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QDialog,
    QDialogButtonBox,
    QPushButton,
)

from frimapper.config import AppConfig  # noqa: E402
from frimapper.db.models import DeviceTemplate, Location  # noqa: E402
from frimapper.domain.enums import DeviceCategory  # noqa: E402
from frimapper.repositories.repositories import (  # noqa: E402
    DeviceRepository,
    LinkRepository,
    LocationRepository,
    TemplateRepository,
)
from frimapper.services.bootstrap import ensure_master_user, initialize_app  # noqa: E402
from frimapper.gui.controllers.auth_controller import AuthController  # noqa: E402
from frimapper.gui.controllers.device_controller import DeviceController  # noqa: E402
from frimapper.gui.controllers.link_controller import LinkController  # noqa: E402
from frimapper.gui.views.dialogs import (  # noqa: E402
    DeviceAttributesDialog,
    DeviceDialog,
    LinkDialog,
)
from frimapper.gui.views.login_view import LoginView  # noqa: E402
from frimapper.gui.views.main_window import MainWindow  # noqa: E402

PASSED = 0
FAILED = 0


def check(name: str, condition: bool) -> None:
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  ok  {name}")
    else:
        FAILED += 1
        print(f"FALHA {name}")


def click_ok(dialog) -> None:
    box = dialog.findChild(QDialogButtonBox)
    QTest.mouseClick(box.button(QDialogButtonBox.Ok), Qt.LeftButton)


def find_button(widget, text: str) -> QPushButton:
    return next(b for b in widget.findChildren(QPushButton) if b.text() == text)


# ------------------------------------------------------------------ setup
ctx = initialize_app(AppConfig.load())
ensure_master_user(ctx)

with ctx.db.session() as s:
    loc = LocationRepository(s, ctx.audit).add(Location(name="Pavilhão A"))
    tpl = TemplateRepository(s, ctx.audit).add(
        DeviceTemplate(
            name="SW-8p", category=DeviceCategory.SWITCH,
            port_count=8, port_prefix="Gi0/",
        )
    )
    devices = DeviceRepository(s, ctx.audit)
    sw = devices.create_from_template("SW-A1", tpl, location_id=loc.id)
    pc = devices.create_from_template(
        "PC-01", None, category=DeviceCategory.COMPUTADOR, location_id=loc.id
    )
    eth0 = devices.add_manual_port(pc, "eth0", "1G")
    LinkRepository(s, ctx.audit).create(sw.ports[0], eth0)
    sw_id, pc_id = sw.id, pc.id

app = QApplication.instance() or QApplication([])
auth = AuthController(ctx)

# ------------------------------------------------------- login por cliques
login = LoginView(auth)
login.show()
QTest.keyClicks(login.username_edit, "master")
QTest.keyClicks(login.password_edit, "ChangeMe123!")
click_ok(login)
check(
    "login: teclado + clique em OK autentica e aceita o diálogo",
    login.session is not None and login.result() == QDialog.Accepted,
)
login.hide()

bad = LoginView(auth)
bad.show()
QTest.keyClicks(bad.username_edit, "master")
QTest.keyClicks(bad.password_edit, "errada")
click_ok(bad)
check(
    "login: clique em OK com password errada mostra erro e não aceita",
    bad.session is None
    and bad.result() != QDialog.Accepted
    and bad.error_label.text() != "",
)
bad.hide()

session = login.session
device_ctl = DeviceController(ctx, session)
link_ctl = LinkController(ctx, session)

# ------------------------------------------------- DeviceDialog por teclado
dialog = DeviceDialog(device_ctl.template_options(), device_ctl.location_options())
dialog.show()
QTest.keyClicks(dialog.hostname_edit, "PC-NOVO")
QTest.keyClicks(dialog.mac_edit, "AA:BB:CC:DD:EE:99")
click_ok(dialog)
form = dialog.form()
check(
    "DeviceDialog: campos preenchidos por teclado chegam ao formulário",
    dialog.result() == QDialog.Accepted
    and form.hostname == "PC-NOVO"
    and form.mac == "AA:BB:CC:DD:EE:99",
)
dialog.hide()

# ------------------------------------ LinkDialog: troca de equipamento
link_devices, free_ports = link_ctl.form_data()
link_dialog = LinkDialog(link_devices, free_ports)
link_dialog.show()
for i in range(link_dialog.device_a_combo.count()):
    if link_dialog.device_a_combo.itemData(i) == sw_id:
        link_dialog.device_a_combo.setCurrentIndex(i)
        break
check(
    "LinkDialog: mudar o equipamento recarrega as portas livres dele",
    link_dialog.port_a_combo.count() == len(free_ports[sw_id]),
)
link_dialog.hide()

# ------------------------------ DeviceAttributesDialog: cliques nos botões
attributes = DeviceAttributesDialog("PC-01", [("Detentor", "João")])
attributes.show()
attributes.suggestion_combo.setCurrentText("RAM")
QTest.mouseClick(find_button(attributes, "Adicionar campo"), Qt.LeftButton)
check(
    "Campos…: clique em 'Adicionar campo' insere a linha sugerida",
    attributes.table.rowCount() == 2
    and attributes.table.item(1, 0).text() == "RAM",
)
attributes.table.setCurrentCell(1, 0)
QTest.mouseClick(find_button(attributes, "Remover selecionado"), Qt.LeftButton)
check(
    "Campos…: clique em 'Remover selecionado' apaga a linha",
    attributes.table.rowCount() == 1 and attributes.pairs() == [("Detentor", "João")],
)
attributes.hide()

# ------------------------------------------- MainWindow: seleção e MapTab
window = MainWindow(ctx, session)
window.show()
devices_tab = window.devices_tab
devices_tab.view.selectRow(0)
check(
    "Equipamentos: selecionar a linha resolve o id do equipamento",
    devices_tab.selected_id() == devices_tab.model.row_id(0),
)

map_tab = window.map_tab
location_index = next(
    i for i in range(map_tab.view_combo.count())
    if map_tab.view_combo.itemData(i) == "location"
)
map_tab.view_combo.setCurrentIndex(location_index)
enabled_for_location = map_tab.location_combo.isEnabled()
map_tab.view_combo.setCurrentIndex(0)
check(
    "Mapa: escolher a vista 'Por localização' ativa o seletor de zona",
    enabled_for_location and not map_tab.location_combo.isEnabled(),
)
window.hide()

# ------------------------------------- ExportDialog: filtro de data (clique)
from frimapper.gui.views.dialogs import ExportDialog, VlanDialog  # noqa: E402

export_dialog = ExportDialog(window.exports)
export_dialog.show()
was_disabled = not export_dialog.since_edit.isEnabled()
QTest.mouseClick(export_dialog.since_check, Qt.LeftButton)
check(
    "Exportação: clique no filtro de data ativa o seletor 'Desde'",
    was_disabled
    and export_dialog.since_edit.isEnabled()
    and export_dialog.maintenance_since() is not None,
)
export_dialog.hide()

# --------------------------------------------- VlanDialog por teclado
vlan_dialog = VlanDialog()
vlan_dialog.show()
vlan_dialog.vlan_id_spin.clear()
QTest.keyClicks(vlan_dialog.vlan_id_spin, "30")
QTest.keyClicks(vlan_dialog.name_edit, "CCTV")
click_ok(vlan_dialog)
vlan_form = vlan_dialog.form()
check(
    "VlanDialog: teclado preenche VLAN ID e nome; OK aceita",
    vlan_dialog.result() == QDialog.Accepted
    and vlan_form.vlan_id == 30
    and vlan_form.name == "CCTV",
)
vlan_dialog.hide()

print(f"\n{PASSED} verificações OK, {FAILED} falhas")
sys.exit(1 if FAILED else 0)
