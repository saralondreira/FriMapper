"""Controller da pesquisa global (com masking do valor encontrado)."""

from __future__ import annotations

from ...security.rbac import Permission, mask_value
from ...services.search_service import SearchService
from ..dto import SearchHit
from .base import BaseController


class SearchController(BaseController):
    def search(self, term: str) -> list[SearchHit]:
        self._require(Permission.VIEW)
        with self.ctx.db.session() as s:
            results = SearchService(s).search(term)
        return [
            SearchHit(
                device_id=r.device_id,
                hostname=r.hostname,
                category=r.category,
                location=r.location,
                matched_field=r.matched_field,
                matched_value=mask_value(
                    self.user.role, r.matched_field, r.matched_value
                ),
                connected_to=r.connected_to,
            )
            for r in results
        ]
