"""Controller de exportação CSV (+ upload SharePoint opcional)."""

from __future__ import annotations

from ...security.rbac import Permission
from ...services.export_service import ExportService
from .base import BaseController


class ExportController(BaseController):
    def export_csv(self, out_dir: str | None = None) -> list[str]:
        self._require(Permission.EXPORT)
        return ExportService(self.ctx).export_all(out_dir)

    def sharepoint_enabled(self) -> bool:
        return self.ctx.config.sharepoint.enabled

    def upload_to_sharepoint(self, files: list[str]) -> list[str]:
        self._require(Permission.EXPORT)
        from ...integrations.sharepoint import SharePointClient  # import tardio

        client = SharePointClient(self.ctx.config.sharepoint)
        return client.upload_many(files)
