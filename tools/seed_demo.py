"""Semeia uma base de demonstração e gera os mapas (requer Graphviz).

Uso: ``python tools/seed_demo.py <pasta-de-dados>`` — a pasta passa a ser o
FRIMAPPER_DATA dessa demo (BD, chave, logs e mapas ficam lá dentro).
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if len(sys.argv) < 2:
    print("uso: python tools/seed_demo.py <pasta-de-dados>")
    raise SystemExit(2)

os.environ["FRIMAPPER_DATA"] = sys.argv[1]

from netmap.config import AppConfig  # noqa: E402
from netmap.db.models import DeviceTemplate, Location  # noqa: E402
from netmap.domain.enums import DeviceCategory, PortStatus  # noqa: E402
from netmap.repositories.repositories import (  # noqa: E402
    DeviceRepository,
    LinkRepository,
    LocationRepository,
    TemplateRepository,
)
from netmap.services.bootstrap import ensure_master_user, initialize_app  # noqa: E402
from netmap.services.map_service import MapService  # noqa: E402

ctx = initialize_app(AppConfig.load())
ensure_master_user(ctx)

with ctx.db.session() as s:
    locations = LocationRepository(s, ctx.audit)
    templates = TemplateRepository(s, ctx.audit)
    devices = DeviceRepository(s, ctx.audit)
    links = LinkRepository(s, ctx.audit)

    sala_ti = locations.add(Location(name="Sala TI"))
    pav_a = locations.add(Location(name="Pavilhão A"))
    bastidor_a = locations.add(Location(name="Bastidor A1", parent_id=pav_a.id))
    pav_b = locations.add(Location(name="Pavilhão B"))

    fw_tpl = templates.add(
        DeviceTemplate(
            name="FortiGate 100F", manufacturer="Fortinet", model="FG-100F",
            category=DeviceCategory.FIREWALL, port_count=8, port_speeds="1G",
            port_prefix="wan",
        )
    )
    sw_tpl = templates.add(
        DeviceTemplate(
            name="Switch 24p", manufacturer="ACME", model="SW-2400",
            category=DeviceCategory.SWITCH, port_count=24, port_speeds="1G",
            port_prefix="Gi0/",
        )
    )

    internet = devices.create_from_template(
        "ISP", None, category=DeviceCategory.INTERNET, location_id=sala_ti.id
    )
    wan = devices.add_manual_port(internet, "uplink", "1G")

    firewall = devices.create_from_template(
        "FW-01", fw_tpl, location_id=sala_ti.id, ip_mgmt="10.0.0.1"
    )
    core = devices.create_from_template(
        "SW-CORE", sw_tpl, location_id=sala_ti.id, ip_mgmt="10.0.0.2"
    )
    sw_a = devices.create_from_template(
        "SW-A1", sw_tpl, location_id=bastidor_a.id, ip_mgmt="10.0.1.2"
    )
    server = devices.create_from_template(
        "SRV-FILES", None, category=DeviceCategory.SERVIDOR,
        location_id=sala_ti.id, ip_mgmt="10.0.0.10",
        snmp_community="demo-community",
    )
    srv_port = devices.add_manual_port(server, "eth0", "10G")

    pc1 = devices.create_from_template(
        "PC-CONTAB", None, category=DeviceCategory.COMPUTADOR,
        location_id=pav_a.id, mac="AA:11:22:33:44:01", assigned_user="maria.santos",
    )
    pc1_port = devices.add_manual_port(pc1, "eth0", "1G")
    devices.set_attributes(
        pc1, [("Detentor", "Maria Santos"), ("RAM", "16GB"), ("CPU", "i5-12400")]
    )

    cam = devices.create_from_template(
        "CAM-PORTARIA", None, category=DeviceCategory.CAMARAS,
        location_id=pav_b.id, ip_mgmt="10.0.2.31",
    )
    cam_port = devices.add_manual_port(cam, "eth0", "100M")

    plc = devices.create_from_template(
        "PLC-LINHA1", None, category=DeviceCategory.AUTOMATOS,
        location_id=pav_b.id, ip_mgmt="10.0.2.51",
    )
    plc_port = devices.add_manual_port(plc, "eth0", "100M")

    printer = devices.create_from_template(
        "PRN-RC", None, category=DeviceCategory.IMPRESSORA,
        location_id=pav_a.id, ip_mgmt="10.0.1.40",
    )
    prn_port = devices.add_manual_port(printer, "eth0", "100M")

    links.create(wan, firewall.ports[0])
    links.create(firewall.ports[1], core.ports[0])
    links.create(core.ports[1], sw_a.ports[0])
    links.create(core.ports[2], srv_port)
    links.create(sw_a.ports[1], pc1_port)
    links.create(sw_a.ports[2], prn_port)
    links.create(core.ports[3], cam_port)
    # Ligação em baixo — aparece a vermelho tracejado no mapa.
    links.create(core.ports[4], plc_port, status=PortStatus.DOWN)

print("Base de demonstração criada.")

if shutil.which("dot"):
    maps = MapService(ctx)
    for view, location_id in (("full", None), ("core", None), ("location", 2)):
        path = maps.generate(view, location_id)
        print(f"Mapa '{view}': {path}")
else:
    print("Graphviz ausente — mapas não gerados.")
