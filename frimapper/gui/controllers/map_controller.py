"""Controller do mapa de topologia.

NOTA DE THREADING: ``generate()`` é bloqueante (Graphviz) — a View invoca-o
num QThread dedicado (``MapWorker``); o contexto da diagrams é thread-local,
pelo que a chamada corre por inteiro nessa thread (DEVLOG #002).
"""

from __future__ import annotations

from ...security.rbac import Permission
from ...services.map_service import MapService
from ..dto import Option
from .base import BaseController


class MapController(BaseController):
    def __init__(self, ctx, session) -> None:
        super().__init__(ctx, session)
        self._maps = MapService(ctx)

    def is_stale(self) -> bool:
        return self._maps.is_stale()

    def last_path(self) -> str:
        return self._maps.last_map_path()

    def generate(self, view: str = "full", location_id: int | None = None) -> str:
        self._require(Permission.GENERATE_MAP)
        return self._maps.generate(view=view, location_id=location_id)
