"""Smoke test da GUI (offscreen, sem display) — 16 verificações.

Constrói janela, tabs e diálogos para os 3 perfis SEM ``exec()`` — apanha
erros de import/construção que o ``py_compile`` não vê (DEVLOG #012).
Uso: ``QT_QPA_PLATFORM=offscreen python tests/gui_smoke.py``.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_tmp = tempfile.TemporaryDirectory(prefix="frimapper-gui-smoke-")
os.environ["FRIMAPPER_DATA"] = _tmp.name

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from netmap.config import AppConfig  # noqa: E402
from netmap.db.models import DeviceTemplate, Location  # noqa: E402
from netmap.domain.enums import DeviceCategory, Role  # noqa: E402
from netmap.repositories.repositories import (  # noqa: E402
    DeviceRepository,
    LinkRepository,
    LocationRepository,
    TemplateRepository,
)
from netmap.security.rbac import MASK  # noqa: E402
from netmap.services.bootstrap import ensure_master_user, initialize_app  # noqa: E402
from netmap.services.user_service import UserService  # noqa: E402
from netmap.gui.controllers.auth_controller import AuthController  # noqa: E402
from netmap.gui.controllers.device_controller import DeviceController  # noqa: E402
from netmap.gui.controllers.link_controller import LinkController  # noqa: E402
from netmap.gui.views.dialogs import (  # noqa: E402
    DeviceAttributesDialog,
    DeviceDialog,
    LinkDialog,
)
from netmap.gui.views.login_view import LoginView  # noqa: E402
from netmap.gui.views.main_window import MainWindow  # noqa: E402
from netmap.gui.views.node_synthesis_view import NodeSynthesisView  # noqa: E402

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


# ------------------------------------------------------------------ setup
ctx = initialize_app(AppConfig.load())
ensure_master_user(ctx)
users = UserService(ctx)
users.create_user("tec1", "Password1!", "Técnico", Role.TECH)
users.create_user("man1", "Password1!", "Manutenção", Role.MAINTENANCE)

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
        "PC-01", None, category=DeviceCategory.COMPUTADOR,
        location_id=loc.id, mac="AA:BB:CC:00:11:22", assigned_user="joao",
    )
    eth0 = devices.add_manual_port(pc, "eth0", "1G")
    LinkRepository(s, ctx.audit).create(sw.ports[0], eth0)
    sw_id, pc_id = sw.id, pc.id

app = QApplication.instance() or QApplication([])
auth = AuthController(ctx)

# ------------------------------------------------------------------ login
login = LoginView(auth)
login.username_edit.setText("master")
login.password_edit.setText("ChangeMe123!")
login._try_login()
check("login com credenciais válidas cria sessão MASTER",
      login.session is not None and login.session.role == Role.MASTER)

bad_login = LoginView(auth)
bad_login.username_edit.setText("master")
bad_login.password_edit.setText("errada")
bad_login._try_login()
check("login com password errada é recusado", bad_login.session is None)

session_master = login.session
session_tech = auth.login("tec1", "Password1!")
session_maint = auth.login("man1", "Password1!")

# ----------------------------------------------------------- MainWindow
ALL_TABS = [
    "Equipamentos", "Ligações", "VLANs", "Firewalls", "Manutenções",
    "Localizações", "Templates", "Mapa", "Utilizadores",
]
window_master = MainWindow(ctx, session_master)
tab_names_master = [
    window_master.tabs.tabText(i) for i in range(window_master.tabs.count())
]
check("MainWindow (Master) tem os 9 separadores", tab_names_master == ALL_TABS)

window_tech = MainWindow(ctx, session_tech)
tab_names_tech = [
    window_tech.tabs.tabText(i) for i in range(window_tech.tabs.count())
]
check("MainWindow (Técnico) não tem separador Utilizadores",
      tab_names_tech == ALL_TABS[:-1])

window_maint = MainWindow(ctx, session_maint)
devices_tab = window_maint.devices_tab
check(
    "Manutenção: botões de escrita desativados (só leitura)",
    not devices_tab.add_button.isEnabled()
    and not devices_tab.edit_button.isEnabled()
    and not devices_tab.delete_button.isEnabled()
    and not devices_tab.fields_button.isEnabled()
    and not devices_tab.export_button.isEnabled(),
)

# ------------------------------------------------------------- masking
model_maint = window_maint.devices_tab.model
model_master = window_master.devices_tab.model
mac_col = 4
pc_row = next(
    r for r in range(model_maint.rowCount())
    if model_maint.row_hostname(r) == "PC-01"
)
check(
    "masking no modelo: Manutenção vê ***",
    model_maint.data(model_maint.index(pc_row, mac_col), Qt.DisplayRole) == MASK,
)
check(
    "masking no modelo: Master vê o valor real",
    model_master.data(model_master.index(pc_row, mac_col), Qt.DisplayRole)
    == "AA:BB:CC:00:11:22",
)

# ------------------------------------------------------------- diálogos
device_ctl = DeviceController(ctx, session_master)
device_dialog = DeviceDialog(
    device_ctl.template_options(), device_ctl.location_options(),
    device_ctl.get_form(pc_id),
)
check("DeviceDialog carrega e devolve o formulário",
      device_dialog.form().hostname == "PC-01")

link_ctl = LinkController(ctx, session_master)
link_devices, free_ports = link_ctl.form_data()
link_dialog = LinkDialog(link_devices, free_ports)
check(
    "LinkDialog só apresenta portas livres (Gi0/1 ocupada excluída)",
    len(free_ports[sw_id]) == 7
    and all("Gi0/1 " not in opt.label and opt.label != "Gi0/1"
            for opt in free_ports[sw_id]),
)

attributes_dialog = DeviceAttributesDialog("PC-01", [("Detentor", "João")])
attributes_dialog._append_row("RAM", "16GB")
check("DeviceAttributesDialog lê/edita pares chave-valor",
      attributes_dialog.pairs() == [("Detentor", "João"), ("RAM", "16GB")])

synthesis_view = NodeSynthesisView(device_ctl.synthesis(sw_id), session_master)
check("NodeSynthesisView constrói a tabela de portas",
      synthesis_view.table.rowCount() == 8)

# -------------------------------------- novos separadores e janelas CRUD
from netmap.gui.controllers.vlan_controller import VlanController  # noqa: E402
from netmap.gui.dto import VlanForm  # noqa: E402

vlan_ctl = VlanController(ctx, session_master)
vlan_ctl.create(VlanForm(vlan_id=20, name="Escritório"))
window_master.vlans_tab.refresh()
check(
    "VlansTab lista o catálogo com contagem de utilização",
    window_master.vlans_tab.table.rowCount() == 1
    and window_master.vlans_tab.table.item(0, 0).text() == "20",
)

links_tab = window_master.links_tab
check(
    "LinksTab lista a ligação SW-A1:Gi0/1 ↔ PC-01:eth0",
    links_tab.table.rowCount() == 1
    and links_tab.table.item(0, 0).text() == "SW-A1"
    and links_tab.table.item(0, 3).text() == "eth0",
)

from netmap.gui.controllers.port_controller import PortController  # noqa: E402
from netmap.gui.views.ports_dialog import PortsDialog  # noqa: E402

ports_dialog = PortsDialog(
    PortController(ctx, session_master), sw_id, "SW-A1", session_master,
    vlan_options=vlan_ctl.labels(),
)
check(
    "PortsDialog lista as 8 portas do switch (1 ligada)",
    ports_dialog.table.rowCount() == 8
    and ports_dialog.table.item(0, 5).text() == "PC-01:eth0",
)

from netmap.gui.views.dialogs import ExportDialog  # noqa: E402
from datetime import datetime  # noqa: E402

export_dialog = ExportDialog(window_master.exports)
check(
    "ExportDialog mostra a data e a pasta com timestamp",
    str(datetime.now().year) in export_dialog.date_label.text()
    and "export_" in export_dialog.folder_label.text(),
)

# ------------------------------------------------------- banner de órfãos
with ctx.db.session() as s:
    repo = DeviceRepository(s, ctx.audit)
    from netmap.services.integrity_service import IntegrityService

    integrity = IntegrityService(s)
    peers = integrity.link_peers({sw_id})
    repo.delete(repo.get(sw_id), force=True)
    integrity.mark_orphans(peers)

window_master.refresh_banners()
check(
    "banner laranja de órfãos visível após force-delete",
    not window_master.orphan_banner.isHidden()
    and "PC-01" in window_master.orphan_banner.text(),
)

print(f"\n{PASSED} verificações OK, {FAILED} falhas")
sys.exit(1 if FAILED else 0)
