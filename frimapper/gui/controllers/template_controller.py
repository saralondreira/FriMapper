"""Controller do catálogo de modelos de equipamento."""

from __future__ import annotations

from sqlalchemy import select

from ...db.models import DeviceTemplate
from ...domain.enums import DeviceCategory
from ...repositories.repositories import TemplateRepository
from ...security.rbac import Permission
from ..dto import TemplateForm, TemplateRow
from .base import BaseController


class TemplateController(BaseController):
    def list_rows(self) -> list[TemplateRow]:
        self._require(Permission.VIEW)
        with self.ctx.db.session() as s:
            return [
                TemplateRow(
                    id=t.id,
                    name=t.name,
                    manufacturer=t.manufacturer or "",
                    model=t.model or "",
                    category=t.category.value,
                    port_count=t.port_count,
                )
                for t in s.scalars(
                    select(DeviceTemplate).order_by(DeviceTemplate.name)
                )
            ]

    def get_form(self, template_id: int) -> TemplateForm:
        with self.ctx.db.session() as s:
            t = s.get(DeviceTemplate, template_id)
            return TemplateForm(
                name=t.name,
                manufacturer=t.manufacturer or "",
                model=t.model or "",
                category=t.category.value,
                port_count=t.port_count,
                port_speeds=t.port_speeds or "",
                port_prefix=t.port_prefix or "Port",
                is_passive=t.is_passive,
            )

    def create(self, form: TemplateForm) -> int:
        self._require(Permission.CREATE)
        if not form.name.strip():
            raise ValueError("O nome do modelo é obrigatório.")
        with self.ctx.db.session() as s:
            repo = TemplateRepository(s, self.ctx.audit)
            template = repo.add(DeviceTemplate(**self._fields(form)))
            return template.id

    def update(self, template_id: int, form: TemplateForm) -> None:
        self._require(Permission.EDIT)
        with self.ctx.db.session() as s:
            repo = TemplateRepository(s, self.ctx.audit)
            repo.update(repo.get(template_id), **self._fields(form))

    def delete(self, template_id: int, force: bool = False) -> list[str]:
        """Force-delete desassocia equipamentos (nunca gera órfãos)."""
        self._require(Permission.FORCE_DELETE if force else Permission.DELETE)
        with self.ctx.db.session() as s:
            repo = TemplateRepository(s, self.ctx.audit)
            repo.delete(repo.get(template_id), force=force)
            return []

    @staticmethod
    def _fields(form: TemplateForm) -> dict:
        category = DeviceCategory(form.category)
        return {
            "name": form.name.strip(),
            "manufacturer": form.manufacturer,
            "model": form.model,
            "category": category,
            "port_count": max(0, int(form.port_count)),
            "port_speeds": form.port_speeds,
            "port_prefix": form.port_prefix or "Port",
            "is_passive": form.is_passive or category.is_passive,
        }
