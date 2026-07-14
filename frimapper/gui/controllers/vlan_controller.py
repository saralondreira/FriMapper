"""Controller do catálogo de VLANs."""

from __future__ import annotations

from sqlalchemy import select

from ...db.models import Vlan
from ...repositories.repositories import VlanRepository
from ...security.rbac import Permission
from ..dto import VlanForm, VlanRow
from .base import BaseController


class VlanController(BaseController):
    def list_rows(self) -> list[VlanRow]:
        self._require(Permission.VIEW)
        with self.ctx.db.session() as s:
            repo = VlanRepository(s, self.ctx.audit)
            rows = []
            for vlan in s.scalars(select(Vlan).order_by(Vlan.vlan_id)):
                devices, ports = repo._users_of(vlan)
                rows.append(
                    VlanRow(
                        id=vlan.id,
                        vlan_id=vlan.vlan_id,
                        name=vlan.name or "",
                        description=vlan.description or "",
                        usage_count=len(devices) + len(ports),
                    )
                )
            return rows

    def labels(self) -> list[str]:
        """Valores para os dropdowns editáveis de VLAN (campo texto)."""
        with self.ctx.db.session() as s:
            return [
                str(v.vlan_id)
                for v in s.scalars(select(Vlan).order_by(Vlan.vlan_id))
            ]

    def get_form(self, vlan_id: int) -> VlanForm:
        with self.ctx.db.session() as s:
            vlan = s.get(Vlan, vlan_id)
            return VlanForm(
                vlan_id=vlan.vlan_id,
                name=vlan.name or "",
                description=vlan.description or "",
            )

    def create(self, form: VlanForm) -> int:
        self._require(Permission.CREATE)
        self._validate(form)
        with self.ctx.db.session() as s:
            repo = VlanRepository(s, self.ctx.audit)
            if repo.by_vlan_id(form.vlan_id) is not None:
                raise ValueError(f"A VLAN {form.vlan_id} já existe no catálogo.")
            vlan = repo.add(
                Vlan(vlan_id=form.vlan_id, name=form.name, description=form.description)
            )
            return vlan.id

    def update(self, row_id: int, form: VlanForm) -> None:
        self._require(Permission.EDIT)
        self._validate(form)
        with self.ctx.db.session() as s:
            repo = VlanRepository(s, self.ctx.audit)
            existing = repo.by_vlan_id(form.vlan_id)
            if existing is not None and existing.id != row_id:
                raise ValueError(f"A VLAN {form.vlan_id} já existe no catálogo.")
            repo.update(
                repo.get(row_id),
                vlan_id=form.vlan_id,
                name=form.name,
                description=form.description,
            )

    def delete(self, row_id: int, force: bool = False) -> list[str]:
        """Bloqueada se em uso; com force limpa o campo VLAN nos utilizadores."""
        self._require(Permission.FORCE_DELETE if force else Permission.DELETE)
        with self.ctx.db.session() as s:
            repo = VlanRepository(s, self.ctx.audit)
            repo.delete(repo.get(row_id), force=force)
            return []

    @staticmethod
    def _validate(form: VlanForm) -> None:
        if not 1 <= int(form.vlan_id) <= 4094:
            raise ValueError("O VLAN ID tem de estar entre 1 e 4094.")
