"""Conector opcional para publicar CSV/artefactos no SharePoint (Microsoft Graph).

DESLIGADO POR DEFEITO — ativa-se em ``config.ini`` na secção ``[sharepoint]``.
Import tardio: ``msal`` e ``requests`` são dependências OPCIONAIS, não de
runtime — a aplicação funciona sem elas.

Segurança (ver DEVLOG #008):
- O ``client_secret`` vem SEMPRE da env var ``FRIMAPPER_SP_CLIENT_SECRET``,
  nunca de ficheiro versionado ou de configuração em disco.
- A chave Fernet (``secret.key``) NUNCA deve ser publicada no SharePoint —
  o backup normal é o CSV, onde as credenciais já saem como ``[protegido]``.

Requisitos no tenant: app registada no Entra ID com permissão de aplicação
``Sites.ReadWrite.All`` (consentimento de administrador).

Ficheiros > 4 MB usam *upload session* da Graph API (chunks múltiplos de
320 KiB) — implementado, por validar num tenant real (ver DEVLOG #017).
"""

from __future__ import annotations

import os
from pathlib import Path

from ..config import SharePointConfig

_SIMPLE_UPLOAD_LIMIT = 4 * 1024 * 1024  # limite do PUT simples da Graph API
# Os chunks do upload session têm de ser múltiplos de 320 KiB (Graph API).
_CHUNK_SIZE = 10 * 320 * 1024


class SharePointError(RuntimeError):
    """Erro amigável do conector (configuração, autenticação ou upload)."""


class SharePointClient:
    GRAPH = "https://graph.microsoft.com/v1.0"

    def __init__(self, config: SharePointConfig) -> None:
        if not config.enabled:
            raise SharePointError(
                "Conector SharePoint desativado (config.ini [sharepoint] enabled)."
            )
        for field in ("tenant_id", "client_id", "site", "folder"):
            if not getattr(config, field):
                raise SharePointError(f"[sharepoint] {field} não configurado.")
        secret = os.environ.get("FRIMAPPER_SP_CLIENT_SECRET")
        if not secret:
            raise SharePointError(
                "Env var FRIMAPPER_SP_CLIENT_SECRET não definida "
                "(o client_secret nunca vive em ficheiros)."
            )
        try:
            import msal
            import requests
        except ImportError as exc:
            raise SharePointError(
                "Dependências opcionais em falta: pip install msal requests"
            ) from exc

        self._requests = requests
        self.config = config
        app = msal.ConfidentialClientApplication(
            config.client_id,
            authority=f"https://login.microsoftonline.com/{config.tenant_id}",
            client_credential=secret,
        )
        token = app.acquire_token_for_client(
            scopes=["https://graph.microsoft.com/.default"]
        )
        if "access_token" not in token:
            raise SharePointError(
                token.get("error_description", "Falha na autenticação Graph.")
            )
        self._headers = {"Authorization": f"Bearer {token['access_token']}"}
        self._site_id: str | None = None

    def _site(self) -> str:
        if self._site_id is None:
            response = self._requests.get(
                f"{self.GRAPH}/sites/{self.config.site}",
                headers=self._headers,
                timeout=30,
            )
            if response.status_code != 200:
                raise SharePointError(f"Site não encontrado: {response.text}")
            self._site_id = response.json()["id"]
        return self._site_id

    def upload(self, local_path: str | Path) -> str:
        """Envia um ficheiro para a pasta configurada; devolve o webUrl."""
        path = Path(local_path)
        if not path.is_file():
            raise SharePointError(f"Ficheiro inexistente: {path}")
        if path.stat().st_size > _SIMPLE_UPLOAD_LIMIT:
            return self._upload_large(path)
        url = (
            f"{self.GRAPH}/sites/{self._site()}/drive/root:"
            f"/{self.config.folder}/{path.name}:/content"
        )
        response = self._requests.put(
            url,
            headers={**self._headers, "Content-Type": "application/octet-stream"},
            data=path.read_bytes(),
            timeout=120,
        )
        if response.status_code not in (200, 201):
            raise SharePointError(f"Upload falhou ({response.status_code}): {response.text}")
        return response.json().get("webUrl", "")

    def _upload_large(self, path: Path) -> str:
        """Upload session da Graph API para ficheiros > 4 MB (chunked PUT)."""
        url = (
            f"{self.GRAPH}/sites/{self._site()}/drive/root:"
            f"/{self.config.folder}/{path.name}:/createUploadSession"
        )
        response = self._requests.post(
            url,
            headers=self._headers,
            json={"item": {"@microsoft.graph.conflictBehavior": "replace"}},
            timeout=30,
        )
        if response.status_code not in (200, 201):
            raise SharePointError(
                f"createUploadSession falhou ({response.status_code}): {response.text}"
            )
        upload_url = response.json()["uploadUrl"]
        size = path.stat().st_size
        web_url = ""
        with open(path, "rb") as fh:
            offset = 0
            while offset < size:
                chunk = fh.read(_CHUNK_SIZE)
                end = offset + len(chunk) - 1
                # O uploadUrl já vem pré-autorizado — sem header Authorization.
                result = self._requests.put(
                    upload_url,
                    headers={
                        "Content-Length": str(len(chunk)),
                        "Content-Range": f"bytes {offset}-{end}/{size}",
                    },
                    data=chunk,
                    timeout=300,
                )
                if result.status_code not in (200, 201, 202):
                    raise SharePointError(
                        f"Chunk {offset}-{end} falhou "
                        f"({result.status_code}): {result.text}"
                    )
                if result.status_code in (200, 201):
                    web_url = result.json().get("webUrl", "")
                offset += len(chunk)
        return web_url

    def upload_many(self, paths: list[str | Path]) -> list[str]:
        return [self.upload(p) for p in paths]
