"""Controller de registos de manutenção (com datas)."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select

from ...db.models import Device, MaintenanceRecord
from ...domain.enums import MaintenanceStatus
from ...repositories.repositories import MaintenanceRepository
from ...security.rbac import Permission
from ..dto import MaintenanceForm, MaintenanceRow, Option
from .base import BaseController


class MaintenanceController(BaseController):
    def list_rows(self, device_id: int | None = None) -> list[MaintenanceRow]:
        self._require(Permission.VIEW)
        with self.ctx.db.session() as s:
            stmt = select(MaintenanceRecord).order_by(
                MaintenanceRecord.date.desc(), MaintenanceRecord.id.desc()
            )
            if device_id is not None:
                stmt = stmt.where(MaintenanceRecord.device_id == device_id)
            return [
                MaintenanceRow(
                    id=m.id,
                    hostname=m.device.hostname,
                    date=m.date.isoformat(),
                    next_due=m.next_due.isoformat() if m.next_due else "",
                    status=m.status.label,
                    technician=m.technician or "",
                    description=m.description or "",
                )
                for m in s.scalars(stmt)
            ]

    def device_options(self) -> list[Option]:
        with self.ctx.db.session() as s:
            return [
                Option(d.id, d.hostname)
                for d in s.scalars(select(Device).order_by(Device.hostname))
            ]

    def get_form(self, row_id: int) -> MaintenanceForm:
        with self.ctx.db.session() as s:
            m = s.get(MaintenanceRecord, row_id)
            return MaintenanceForm(
                device_id=m.device_id,
                date=m.date.isoformat(),
                next_due=m.next_due.isoformat() if m.next_due else "",
                status=m.status.value,
                technician=m.technician or "",
                description=m.description or "",
            )

    def create(self, form: MaintenanceForm) -> int:
        self._require(Permission.CREATE)
        with self.ctx.db.session() as s:
            repo = MaintenanceRepository(s, self.ctx.audit)
            record = repo.add(MaintenanceRecord(**self._fields(form)))
            return record.id

    def update(self, row_id: int, form: MaintenanceForm) -> None:
        self._require(Permission.EDIT)
        with self.ctx.db.session() as s:
            repo = MaintenanceRepository(s, self.ctx.audit)
            repo.update(repo.get(row_id), **self._fields(form))

    def delete(self, row_id: int, force: bool = False) -> list[str]:
        self._require(Permission.DELETE)
        with self.ctx.db.session() as s:
            repo = MaintenanceRepository(s, self.ctx.audit)
            repo.delete(repo.get(row_id))
            return []

    @staticmethod
    def _fields(form: MaintenanceForm) -> dict:
        if form.device_id is None:
            raise ValueError("Escolha o equipamento.")
        if not form.date:
            raise ValueError("A data da manutenção é obrigatória.")
        return {
            "device_id": form.device_id,
            "date": date.fromisoformat(form.date),
            "next_due": date.fromisoformat(form.next_due) if form.next_due else None,
            "status": MaintenanceStatus(form.status),
            "technician": form.technician,
            "description": form.description,
        }
