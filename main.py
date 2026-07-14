"""Frimapper — ponto de entrada.

Uso:
    python main.py             arranca a aplicação (login + janela principal)
    python main.py --selftest  valida o núcleo sem GUI (também usado para
                               verificar o executável empacotado)
"""

from __future__ import annotations

import os
import sys
import tempfile


def run_selftest() -> int:
    """Bootstrap + CRUD mínimo numa pasta temporária; devolve exit code."""
    failures = 0

    def check(name: str, condition: bool) -> None:
        nonlocal failures
        print(f"{'  ok ' if condition else 'FALHA'} {name}")
        if not condition:
            failures += 1

    with tempfile.TemporaryDirectory(prefix="frimapper-selftest-") as tmp:
        os.environ["FRIMAPPER_DATA"] = tmp

        from netmap.config import AppConfig
        from netmap.db.models import DeviceTemplate
        from netmap.domain.enums import DeviceCategory, Role
        from netmap.repositories.repositories import (
            DeviceRepository,
            LinkRepository,
            TemplateRepository,
        )
        from netmap.services.bootstrap import ensure_master_user, initialize_app
        from netmap.services.search_service import SearchService
        from netmap.services.user_service import UserService

        ctx = initialize_app(AppConfig.load())
        check("bootstrap (BD + cifra + auditoria)", True)
        check("master criado", ensure_master_user(ctx))
        users = UserService(ctx)
        check(
            "login do master",
            users.authenticate("master", "ChangeMe123!") is not None,
        )
        check("RBAC ativo", Role.MAINTENANCE.value == "maintenance")
        with ctx.db.session() as s:
            tpl = TemplateRepository(s, ctx.audit).add(
                DeviceTemplate(
                    name="ST-SW", category=DeviceCategory.SWITCH,
                    port_count=2, port_prefix="P",
                )
            )
            dev_repo = DeviceRepository(s, ctx.audit)
            sw = dev_repo.create_from_template("ST-SW1", tpl)
            pc = dev_repo.create_from_template(
                "ST-PC1", None,
                category=DeviceCategory.COMPUTADOR, mac="00:11:22:33:44:55",
            )
            eth = dev_repo.add_manual_port(pc, "eth0")
            LinkRepository(s, ctx.audit).create(sw.ports[0], eth)
            check("template/ligação", len(sw.ports) == 2)
            check(
                "pesquisa",
                any(
                    r.hostname == "ST-PC1"
                    for r in SearchService(s).search("00:11:22")
                ),
            )
        import shutil

        check("ícones empacotados", os.path.isdir(ctx.config.icon_dir))
        if shutil.which("dot"):
            from netmap.services.map_service import MapService

            png = MapService(ctx).generate("full")
            check("geração de mapa PNG", os.path.isfile(png))
        else:
            print("  --  Graphviz ausente: geração de mapa não testada")

    print(f"\nSelftest: {'OK' if not failures else f'{failures} falhas'}")
    return 1 if failures else 0


def run_gui() -> int:
    from PySide6.QtWidgets import QApplication, QDialog

    from netmap.config import AppConfig
    from netmap.gui.controllers.auth_controller import AuthController
    from netmap.gui.views.login_view import LoginView
    from netmap.gui.views.main_window import MainWindow
    from netmap.services.bootstrap import ensure_master_user, initialize_app

    ctx = initialize_app(AppConfig.load())
    first_run = ensure_master_user(ctx)

    app = QApplication(sys.argv)
    app.setApplicationName("Frimapper")
    login = LoginView(AuthController(ctx), first_run=first_run)
    if login.exec() != QDialog.Accepted or login.session is None:
        return 0
    window = MainWindow(ctx, login.session)
    window.show()
    return app.exec()


def main() -> int:
    if "--selftest" in sys.argv:
        return run_selftest()
    return run_gui()


if __name__ == "__main__":
    sys.exit(main())
