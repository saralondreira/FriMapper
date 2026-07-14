"""Controller de zonas/localizações."""

from __future__ import annotations

from sqlalchemy import select

from ...db.models import Location
from ...repositories.repositories import LocationRepository
from ...security.rbac import Permission
from ...services.integrity_service import IntegrityService
from ..dto import LocationForm, LocationRow, Option
from .base import BaseController


class LocationController(BaseController):
    def list_rows(self) -> list[LocationRow]:
        self._require(Permission.VIEW)
        with self.ctx.db.session() as s:
            return [
                LocationRow(
                    id=loc.id,
                    name=loc.name,
                    description=loc.description or "",
                    parent=loc.parent.name if loc.parent else "",
                )
                for loc in s.scalars(select(Location).order_by(Location.name))
            ]

    def options(self, exclude_id: int | None = None) -> list[Option]:
        with self.ctx.db.session() as s:
            options = [Option(None, "— sem zona-pai —")]
            for loc in s.scalars(select(Location).order_by(Location.name)):
                if loc.id != exclude_id:
                    options.append(Option(loc.id, loc.name))
            return options

    def get_form(self, location_id: int) -> LocationForm:
        with self.ctx.db.session() as s:
            loc = s.get(Location, location_id)
            return LocationForm(
                name=loc.name,
                description=loc.description or "",
                parent_id=loc.parent_id,
            )

    def create(self, form: LocationForm) -> int:
        self._require(Permission.CREATE)
        if not form.name.strip():
            raise ValueError("O nome da zona é obrigatório.")
        with self.ctx.db.session() as s:
            repo = LocationRepository(s, self.ctx.audit)
            loc = repo.add(
                Location(
                    name=form.name.strip(),
                    description=form.description,
                    parent_id=form.parent_id,
                )
            )
            return loc.id

    def update(self, location_id: int, form: LocationForm) -> None:
        self._require(Permission.EDIT)
        if form.parent_id == location_id:
            raise ValueError("Uma zona não pode ser pai de si própria.")
        with self.ctx.db.session() as s:
            repo = LocationRepository(s, self.ctx.audit)
            repo.update(
                repo.get(location_id),
                name=form.name.strip(),
                description=form.description,
                parent_id=form.parent_id,
            )

    def delete(self, location_id: int, force: bool = False) -> list[str]:
        """Elimina a zona; com force devolve os hostnames que ficaram órfãos."""
        self._require(Permission.FORCE_DELETE if force else Permission.DELETE)
        with self.ctx.db.session() as s:
            repo = LocationRepository(s, self.ctx.audit)
            integrity = IntegrityService(s)
            location = repo.get(location_id)
            peers: set[int] = set()
            if force:
                doomed = integrity.device_ids_in_location(location_id)
                peers = integrity.link_peers(doomed)
            repo.delete(location, force=force)  # DependencyError propaga
            return integrity.mark_orphans(peers) if force else []
