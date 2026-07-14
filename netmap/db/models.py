"""Modelos ORM (SQLAlchemy 2.0, estilo ``Mapped``).

Ver docs/MANUAL.md §6 para o dicionário de dados completo. As relações com
``cascade="all, delete-orphan"`` (ports/attributes de Device) só são
exercitadas no force-delete — a eliminação normal é bloqueada pela camada de
repositórios quando existem dependências.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..domain.enums import (
    DeviceCategory,
    DeviceStatus,
    LinkType,
    MaintenanceStatus,
    PortStatus,
    Role,
)
from .base import Base
from .types import EncryptedString


def _enum(enum_cls):
    """Enum guardado como VARCHAR (portável entre motores de BD)."""
    return SAEnum(
        enum_cls,
        native_enum=False,
        length=32,
        values_callable=lambda e: [member.value for member in e],
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(128), default="")
    role: Mapped[Role] = mapped_column(_enum(Role), default=Role.MAINTENANCE)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User {self.username} ({self.role.value})>"


class Location(TimestampMixin, Base):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    description: Mapped[str] = mapped_column(String(255), default="")
    parent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("locations.id"), nullable=True
    )

    parent: Mapped[Optional["Location"]] = relationship(
        "Location", remote_side="Location.id", back_populates="children"
    )
    children: Mapped[list["Location"]] = relationship(
        "Location", back_populates="parent"
    )
    devices: Mapped[list["Device"]] = relationship(
        "Device", back_populates="location"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Location {self.name}>"


class DeviceTemplate(TimestampMixin, Base):
    __tablename__ = "device_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    manufacturer: Mapped[str] = mapped_column(String(128), default="")
    model: Mapped[str] = mapped_column(String(128), default="")
    category: Mapped[DeviceCategory] = mapped_column(
        _enum(DeviceCategory), default=DeviceCategory.SWITCH
    )
    port_count: Mapped[int] = mapped_column(Integer, default=0)
    port_speeds: Mapped[str] = mapped_column(String(128), default="1G")
    port_prefix: Mapped[str] = mapped_column(String(32), default="Port")
    is_passive: Mapped[bool] = mapped_column(Boolean, default=False)

    devices: Mapped[list["Device"]] = relationship(
        "Device", back_populates="template"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<DeviceTemplate {self.name}>"


class Device(TimestampMixin, Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hostname: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    category: Mapped[DeviceCategory] = mapped_column(
        _enum(DeviceCategory), default=DeviceCategory.COMPUTADOR
    )
    template_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("device_templates.id"), nullable=True
    )
    location_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("locations.id"), nullable=True
    )
    status: Mapped[DeviceStatus] = mapped_column(
        _enum(DeviceStatus), default=DeviceStatus.UNKNOWN
    )
    needs_relink: Mapped[bool] = mapped_column(Boolean, default=False)

    ip_mgmt: Mapped[str] = mapped_column(String(64), default="")
    mac: Mapped[str] = mapped_column(String(64), default="")
    vlan: Mapped[str] = mapped_column(String(64), default="")
    os_detected: Mapped[str] = mapped_column(String(128), default="")
    assigned_user: Mapped[str] = mapped_column(String(128), default="")
    serial_number: Mapped[str] = mapped_column(String(128), default="")
    notes: Mapped[str] = mapped_column(Text, default="")

    # Cifrados em repouso (Fernet) — ver db/types.EncryptedString
    snmp_community: Mapped[Optional[str]] = mapped_column(
        EncryptedString(512), nullable=True
    )
    access_password: Mapped[Optional[str]] = mapped_column(
        EncryptedString(512), nullable=True
    )

    template: Mapped[Optional[DeviceTemplate]] = relationship(
        "DeviceTemplate", back_populates="devices"
    )
    location: Mapped[Optional[Location]] = relationship(
        "Location", back_populates="devices"
    )
    ports: Mapped[list["Port"]] = relationship(
        "Port",
        back_populates="device",
        cascade="all, delete-orphan",
        order_by="Port.id",
    )
    attributes: Mapped[list["DeviceAttribute"]] = relationship(
        "DeviceAttribute",
        back_populates="device",
        cascade="all, delete-orphan",
        order_by="DeviceAttribute.name",
    )
    maintenances: Mapped[list["MaintenanceRecord"]] = relationship(
        "MaintenanceRecord",
        back_populates="device",
        cascade="all, delete-orphan",
        order_by="MaintenanceRecord.date.desc()",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Device {self.hostname} ({self.category.value})>"


class Port(TimestampMixin, Base):
    __tablename__ = "ports"
    __table_args__ = (UniqueConstraint("device_id", "name", name="uq_port_device_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(64))
    speed: Mapped[str] = mapped_column(String(32), default="")
    status: Mapped[PortStatus] = mapped_column(
        _enum(PortStatus), default=PortStatus.UNUSED
    )
    vlan: Mapped[str] = mapped_column(String(64), default="")
    is_uplink: Mapped[bool] = mapped_column(Boolean, default=False)

    device: Mapped[Device] = relationship("Device", back_populates="ports")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Port {self.name}@{self.device_id}>"


class Link(TimestampMixin, Base):
    __tablename__ = "links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    port_a_id: Mapped[int] = mapped_column(ForeignKey("ports.id"), nullable=False)
    port_b_id: Mapped[int] = mapped_column(ForeignKey("ports.id"), nullable=False)
    link_type: Mapped[LinkType] = mapped_column(
        _enum(LinkType), default=LinkType.ACTIVE
    )
    status: Mapped[PortStatus] = mapped_column(
        _enum(PortStatus), default=PortStatus.UP
    )
    notes: Mapped[str] = mapped_column(String(255), default="")

    port_a: Mapped[Port] = relationship("Port", foreign_keys=[port_a_id])
    port_b: Mapped[Port] = relationship("Port", foreign_keys=[port_b_id])

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Link {self.port_a_id}<->{self.port_b_id}>"


class DeviceAttribute(TimestampMixin, Base):
    """Campo dinâmico por equipamento (modelo EAV: chave-valor livre)."""

    __tablename__ = "device_attributes"
    __table_args__ = (
        UniqueConstraint("device_id", "name", name="uq_attr_device_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(128))
    value: Mapped[str] = mapped_column(Text, default="")

    device: Mapped[Device] = relationship("Device", back_populates="attributes")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<DeviceAttribute {self.name}={self.value!r}>"


class Vlan(TimestampMixin, Base):
    """Catálogo de VLANs.

    Tabela ADITIVA: os campos ``Device.vlan``/``Port.vlan`` continuam texto
    (compatibilidade com BDs existentes até haver migrações Alembic); o
    catálogo alimenta os dropdowns e valida a eliminação por correspondência
    exata com ``str(vlan_id)``.
    """

    __tablename__ = "vlans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vlan_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128), default="")
    description: Mapped[str] = mapped_column(String(255), default="")

    @property
    def label(self) -> str:
        return f"{self.vlan_id} — {self.name}" if self.name else str(self.vlan_id)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Vlan {self.vlan_id} {self.name!r}>"


class MaintenanceRecord(TimestampMixin, Base):
    """Registo de manutenção de um equipamento (agendada/realizada), com datas.

    O histórico morre com o equipamento (cascade ORM) — não bloqueia a
    eliminação, ao contrário das portas ocupadas.
    """

    __tablename__ = "maintenance_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date)
    next_due: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[MaintenanceStatus] = mapped_column(
        _enum(MaintenanceStatus), default=MaintenanceStatus.PLANNED
    )
    technician: Mapped[str] = mapped_column(String(128), default="")
    description: Mapped[str] = mapped_column(Text, default="")

    device: Mapped[Device] = relationship("Device", back_populates="maintenances")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<MaintenanceRecord {self.device_id}@{self.date}>"


class SystemMeta(Base):
    """Pares chave-valor de sistema.

    Chaves usadas: ``db_last_modified``, ``map_last_generated``,
    ``map_last_path`` (alerta de desatualização do mapa).
    """

    __tablename__ = "system_meta"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(512), default="")
