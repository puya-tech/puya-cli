"""Cliente XML-RPC contra Odoo.

Portado desde puya-odoo-mcp. Capa 1 (low-level) — no sabe de RBAC ni de
approvals. Solo habla con Odoo. Las capas superiores (rbac, audit) lo
envuelven.
"""

from __future__ import annotations

import xmlrpc.client
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from puya.lib.config import Config


class OdooError(Exception):
    pass


class OdooClient:
    def __init__(self, url: str, db: str, login: str, api_key: str):
        self.url = url
        self.db = db
        self.login = login
        self.api_key = api_key
        self.uid: int | None = None
        self._common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common", allow_none=True)
        self._object = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", allow_none=True)

    @classmethod
    def from_config(cls, cfg: Config, *, authenticate: bool = True) -> OdooClient:
        client = cls(cfg.odoo_url, cfg.odoo_db, cfg.odoo_login, cfg.odoo_api_key)
        if authenticate:
            client.authenticate()
        return client

    def authenticate(self) -> int:
        try:
            self.uid = self._common.authenticate(self.db, self.login, self.api_key, {})
        except xmlrpc.client.Fault as e:
            raise OdooError(f"Authentication failed: {e.faultString}") from e
        except xmlrpc.client.ProtocolError as e:
            raise OdooError(f"Connection error: {e.errmsg}") from e

        if not self.uid:
            raise OdooError("Authentication failed: invalid API key or database")
        return self.uid

    def execute_kw(self, model: str, method: str, args: list, kwargs: dict | None = None):
        if self.uid is None:
            raise OdooError("Not authenticated. Call authenticate() first.")
        try:
            return self._object.execute_kw(
                self.db, self.uid, self.api_key, model, method, args, kwargs or {}
            )
        except xmlrpc.client.Fault as e:
            raise OdooError(f"Odoo error on {model}.{method}: {e.faultString}") from e
        except xmlrpc.client.ProtocolError as e:
            raise OdooError(f"Connection error on {model}.{method}: {e.errmsg}") from e

    # ── Helpers de conveniencia ─────────────────────────────
    def search_read(
        self,
        model: str,
        domain: list,
        fields: list[str] | None = None,
        options: dict | None = None,
    ) -> list[dict]:
        opts: dict = dict(options or {})
        if fields:
            opts["fields"] = fields
        return self.execute_kw(model, "search_read", [domain], opts)

    def get_user_role(self) -> str:
        if self.uid is None:
            raise OdooError("Not authenticated. Call authenticate() first.")
        result = self.execute_kw("res.users", "read", [[self.uid]], {"fields": ["x_mcp_role"]})
        if not result:
            raise OdooError("Could not read user data")
        return result[0].get("x_mcp_role") or "vendedor"
