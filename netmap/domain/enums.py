"""Enumerações de domínio — agnósticas à BD e à GUI."""

from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    """Perfis RBAC."""

    MASTER = "master"
    TECH = "tech"
    MAINTENANCE = "maintenance"

    @property
    def label(self) -> str:
        return {
            Role.MASTER: "Admin/Master",
            Role.TECH: "Técnico de Redes",
            Role.MAINTENANCE: "Manutenção",
        }[self]


class DeviceCategory(str, Enum):
    """Categorias de equipamento (lista base com 22 tipos)."""

    INTERNET = "internet"
    ROUTER = "router"
    FIREWALL = "firewall"
    SWITCH = "switch"
    REGUA = "regua"
    SERVIDOR = "servidor"
    UPS = "ups"
    NAS = "nas"
    COMPUTADOR = "computador"
    PORTATIL = "portatil"
    TELEFONE_FIXO = "telefone_fixo"
    TELEFONE = "telefone"
    IMPRESSORA = "impressora"
    AP = "ap"
    CABO_VAZIO = "cabo_vazio"
    CAMARAS = "camaras"
    CCTV = "cctv"
    CONTROLO_ACESSOS = "controlo_acessos"
    AUTOMATOS = "automatos"
    SOLAR = "solar"
    CARREGADOR_EV = "carregador_ev"
    VOIP = "voip"

    @property
    def is_passive(self) -> bool:
        """Equipamentos passivos (sem eletrónica ativa de rede)."""
        return self in (DeviceCategory.REGUA, DeviceCategory.CABO_VAZIO)


class PortStatus(str, Enum):
    UP = "up"
    DOWN = "down"
    UNUSED = "unused"


class LinkType(str, Enum):
    ACTIVE = "active"
    PASSIVE = "passive"


class DeviceStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    UNKNOWN = "unknown"
