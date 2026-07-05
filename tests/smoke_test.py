"""Smoke test do núcleo (sem GUI) — 40 verificações.

Corre contra uma pasta de dados temporária (env FRIMAPPER_DATA), pelo que
nunca toca em dados reais. Uso: ``python tests/smoke_test.py``.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_tmp = tempfile.TemporaryDirectory(prefix="frimapper-smoke-")
os.environ["FRIMAPPER_DATA"] = _tmp.name

from sqlalchemy import text  # noqa: E402

from netmap.config import AppConfig  # noqa: E402
from netmap.db.models import (  # noqa: E402
    DeviceTemplate,
    Location,
    MaintenanceRecord,
    Vlan,
)
from netmap.domain.enums import (  # noqa: E402
    DeviceCategory,
    MaintenanceStatus,
    PortStatus,
    Role,
)
from netmap.repositories.base import DependencyError  # noqa: E402
from netmap.repositories.meta import set_meta  # noqa: E402
from netmap.repositories.repositories import (  # noqa: E402
    DeviceRepository,
    LinkRepository,
    LocationRepository,
    MaintenanceRepository,
    TemplateRepository,
    VlanRepository,
)
from netmap.security.auth import hash_password, verify_password  # noqa: E402
from netmap.security.rbac import (  # noqa: E402
    MASK,
    Permission,
    has_permission,
    mask_value,
)
from netmap.services.bootstrap import ensure_master_user, initialize_app  # noqa: E402
from netmap.services.export_service import ExportService  # noqa: E402
from netmap.services.integrity_service import IntegrityService  # noqa: E402
from netmap.services.map_service import MapService  # noqa: E402
from netmap.services.search_service import SearchService  # noqa: E402
from netmap.services.synthesis_service import SynthesisService  # noqa: E402
from netmap.services.user_service import UserService  # noqa: E402

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


data = Path(_tmp.name)
config = AppConfig.load()
ctx = initialize_app(config)

# ------------------------------------------------------------- bootstrap
check(
    "bootstrap cria a BD SQLite e a chave Fernet (secret.key)",
    (data / "network_inventory.db").is_file() and (data / "secret.key").is_file(),
)
check(
    "master criado no 1º arranque e não recriado no 2º",
    ensure_master_user(ctx) and not ensure_master_user(ctx),
)

# ----------------------------------------------------- hashing / login
h = hash_password("Abc123!")
check(
    "hash de password usa argon2 e valida a password correta",
    h.startswith("$argon2") and verify_password("Abc123!", h),
)
check("verify rejeita password errada", not verify_password("errada", h))

users = UserService(ctx)
master = users.authenticate("master", "ChangeMe123!")
check(
    "authenticate aceita credenciais válidas e rejeita inválidas",
    master is not None and users.authenticate("master", "nope") is None,
)

tech = users.create_user("tec1", "Password1!", "Técnico de Redes", Role.TECH)
check(
    "verify_admin aceita Master e rejeita não-Master",
    users.verify_admin("master", "ChangeMe123!")
    and not users.verify_admin("tec1", "Password1!"),
)

try:
    users.delete_user(master.id)
    last_master_protected = False
except DependencyError:
    last_master_protected = True
check("último Master ativo nunca pode ser eliminado", last_master_protected)

# ---------------------------------------------------------------- RBAC
check(
    "RBAC: TECH sem MANAGE_USERS; MAINTENANCE só VIEW",
    not has_permission(Role.TECH, Permission.MANAGE_USERS)
    and has_permission(Role.MAINTENANCE, Permission.VIEW)
    and not has_permission(Role.MAINTENANCE, Permission.EDIT),
)
check(
    "masking: MAINTENANCE vê *** e TECH vê o valor real",
    mask_value(Role.MAINTENANCE, "mac", "AA:BB") == MASK
    and mask_value(Role.TECH, "mac", "AA:BB") == "AA:BB",
)

# --------------------------------------------- inventário e ligações
with ctx.db.session() as s:
    loc_repo = LocationRepository(s, ctx.audit)
    tpl_repo = TemplateRepository(s, ctx.audit)
    dev_repo = DeviceRepository(s, ctx.audit)
    link_repo = LinkRepository(s, ctx.audit)
    integrity = IntegrityService(s)

    pavilhao = loc_repo.add(Location(name="Pavilhão A"))
    bastidor = loc_repo.add(Location(name="Bastidor A1", parent_id=pavilhao.id))

    template = tpl_repo.add(
        DeviceTemplate(
            name="Switch 4p",
            manufacturer="ACME",
            model="SW-4000",
            category=DeviceCategory.SWITCH,
            port_count=4,
            port_speeds="1G",
            port_prefix="Gi0/",
        )
    )
    switch = dev_repo.create_from_template("SW-A1", template, location_id=bastidor.id)
    check(
        "equipamento herda as portas do modelo (nº e prefixo)",
        len(switch.ports) == 4 and switch.ports[0].name == "Gi0/1",
    )

    pc = dev_repo.create_from_template(
        "PC-01",
        None,
        category=DeviceCategory.COMPUTADOR,
        location_id=pavilhao.id,
        mac="AA:BB:CC:DD:EE:FF",
        assigned_user="joao.silva",
        snmp_community="comunidade-secreta",
        access_password="pw-super-secreta",
    )
    eth0 = dev_repo.add_manual_port(pc, "eth0", "1G")
    eth1 = dev_repo.add_manual_port(pc, "eth1", "1G")

    raw = s.execute(
        text("SELECT snmp_community FROM devices WHERE hostname = :h"),
        {"h": "PC-01"},
    ).scalar()
    check(
        "cifra em repouso: valor na BD não é o texto em claro",
        bool(raw) and raw != "comunidade-secreta",
    )
    s.expire(pc)
    check("decifra transparente ao ler pelo ORM", pc.snmp_community == "comunidade-secreta")

    check("todas as portas livres antes da ligação", len(dev_repo.free_ports(switch)) == 4)
    link_repo.create(switch.ports[0], eth0)
    check("ligação ocupa a porta (dropdowns só mostram livres)",
          len(dev_repo.free_ports(switch)) == 3)
    check("estado das portas fica UP após a ligação",
          switch.ports[0].status == PortStatus.UP and eth0.status == PortStatus.UP)

    try:
        link_repo.create(switch.ports[0], eth1)
        double_link_rejected = False
    except ValueError:
        double_link_rejected = True
    check("ligação a uma porta já ocupada é rejeitada", double_link_rejected)

    # ------------------------------------------ dependências / bloqueios
    try:
        dev_repo.delete(switch)
        blocked, deps = False, []
    except DependencyError as exc:
        blocked, deps = True, exc.dependencies
    check("eliminação de equipamento com porta ligada é bloqueada", blocked)
    check("DependencyError expõe a lista de dependências", len(deps) > 0)

    try:
        tpl_repo.delete(template)
        tpl_blocked = False
    except DependencyError:
        tpl_blocked = True
    check("modelo em uso não pode ser eliminado", tpl_blocked)

    try:
        loc_repo.delete(pavilhao)
        loc_blocked = False
    except DependencyError:
        loc_blocked = True
    check("zona com equipamentos/sub-zonas não pode ser eliminada", loc_blocked)

    # ------------------------------------------------- síntese por nó
    synthesis = SynthesisService(s).for_device(switch)
    check(
        "síntese por nó lista portas, ligado-a e utilizador",
        len(synthesis.ports) == 4
        and synthesis.ports[0].connected_device == "PC-01"
        and synthesis.ports[0].user == "joao.silva",
    )

    # ------------------------------------------ force-delete + órfãos
    peers = integrity.link_peers({switch.id})
    check("peer externo detetado antes do force-delete", pc.id in peers)
    dev_repo.delete(switch, force=True)
    check("force-delete remove o equipamento e os links",
          dev_repo.by_hostname("SW-A1") is None)
    orphans = integrity.mark_orphans(peers)
    check("equipamento que ficou sem ligação é marcado órfão",
          orphans == ["PC-01"] and pc.needs_relink
          and integrity.orphan_hostnames() == ["PC-01"])

    switch2 = dev_repo.create_from_template("SW-A2", template, location_id=bastidor.id)
    link_repo.create(switch2.ports[0], eth0)
    check("nova ligação limpa o alerta de órfão (needs_relink)", not pc.needs_relink)

    tpl_repo.delete(template, force=True)
    check("force-delete de modelo desassocia os equipamentos",
          switch2.template_id is None)

    # ------------------------------------------------ campos dinâmicos
    dev_repo.set_attributes(pc, [("Detentor", "João"), ("RAM", "16GB")])
    dev_repo.set_attributes(pc, [("Detentor", "Maria"), ("CPU", "i5-12400")])
    attrs = {a.name: a.value for a in dev_repo.attributes(pc)}
    check(
        "campos dinâmicos sincronizam (adiciona/atualiza/remove)",
        attrs == {"Detentor": "Maria", "CPU": "i5-12400"},
    )

    # -------------------------------------------------- pesquisa global
    search = SearchService(s)
    by_mac = search.search("AA:BB:CC")
    check(
        "pesquisa global encontra por MAC e por campo dinâmico",
        any(r.hostname == "PC-01" for r in by_mac)
        and any(r.hostname == "PC-01" for r in search.search("Maria")),
    )
    hit = next(r for r in by_mac if r.hostname == "PC-01")
    check("pesquisa devolve o switch/porta onde está ligado",
          "SW-A2:Gi0/1" in hit.connected_to)

# --------------------------------------------- VLANs e manutenções
with ctx.db.session() as s:
    vlan_repo = VlanRepository(s, ctx.audit)
    dev_repo = DeviceRepository(s, ctx.audit)
    maint_repo = MaintenanceRepository(s, ctx.audit)

    vlan10 = vlan_repo.add(Vlan(vlan_id=10, name="Gestão"))
    pc = dev_repo.by_hostname("PC-01")
    dev_repo.update(pc, vlan="10")
    try:
        vlan_repo.delete(vlan10)
        vlan_blocked = False
    except DependencyError:
        vlan_blocked = True
    check("VLAN em uso não pode ser eliminada", vlan_blocked)

    vlan_repo.delete(vlan10, force=True)
    check("force-delete de VLAN limpa o campo nos equipamentos", pc.vlan == "")

    from datetime import date, timedelta

    record = maint_repo.add(
        MaintenanceRecord(
            device_id=pc.id,
            date=date.today(),
            next_due=date.today() + timedelta(days=180),
            status=MaintenanceStatus.DONE,
            technician="tec1",
            description="Limpeza e atualização de firmware",
        )
    )
    check(
        "manutenção registada com data e próxima intervenção",
        len(maint_repo.for_device(pc.id)) == 1
        and record.next_due > record.date,
    )

    temp = dev_repo.create_from_template(
        "TMP-01", None, category=DeviceCategory.COMPUTADOR
    )
    maint_repo.add(MaintenanceRecord(device_id=temp.id, date=date.today()))
    dev_repo.delete(temp)  # sem ligações → eliminação normal
    check(
        "histórico de manutenções morre com o equipamento (cascade)",
        len(maint_repo.for_device(temp.id)) == 0,
    )

# ------------------------------------------------------------- export CSV
files = ExportService(ctx).export_all(data)
check("export cria os 8 ficheiros CSV", len(files) == 8
      and all(Path(f).is_file() for f in files))
from datetime import date as _date, timedelta as _timedelta  # noqa: E402

filtered = ExportService(ctx).export_all(
    data, maintenance_since=_date.today() + _timedelta(days=1)
)
maint_csv = Path(
    [f for f in filtered if f.endswith("manutencoes.csv")][0]
).read_text(encoding="utf-8-sig")
check(
    "export com data filtra as manutenções (só cabeçalho)",
    len(maint_csv.strip().splitlines()) == 1,
)
devices_csv = Path([f for f in files if f.endswith("equipamentos.csv")][0]).read_text(
    encoding="utf-8-sig"
)
check(
    "credenciais cifradas não vazam no export ([protegido])",
    "comunidade-secreta" not in devices_csv
    and "pw-super-secreta" not in devices_csv
    and "[protegido]" in devices_csv,
)

# -------------------------------------------------------------- staleness
maps = MapService(ctx)
check("mapa marcado como desatualizado após alterações na BD", maps.is_stale())
with ctx.db.session() as s:
    from datetime import datetime

    set_meta(s, "map_last_generated", datetime.now().isoformat(timespec="seconds"))
    set_meta(s, "map_last_path", "dummy.png")
check("alerta de staleness limpa após geração do mapa", not maps.is_stale())
check("last_map_path devolve o último PNG", maps.last_map_path() == "dummy.png")

# ------------------------------------------------------------- auditoria
audit_text = Path(ctx.config.audit_log).read_text(encoding="utf-8")
check(
    "audit log regista BOOTSTRAP, LOGIN e FORCE_DELETE",
    "BOOTSTRAP" in audit_text
    and "LOGIN_OK" in audit_text
    and "LOGIN_FAIL" in audit_text
    and "FORCE_DELETE" in audit_text,
)

print(f"\n{PASSED} verificações OK, {FAILED} falhas")
sys.exit(1 if FAILED else 0)
