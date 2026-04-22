"""Bootstrap compartido por todos los comandos de Odoo.

Cada comando llama `setup()` una vez al inicio para tener:
- Config cargada
- RBAC engine inicializado
- OdooClient autenticado
- AuditLogger
- username (login del user con el que conectamos)

Mantiene los comandos chicos y consistentes.
"""

from __future__ import annotations

from dataclasses import dataclass

from puya.lib.audit import AuditLogger
from puya.lib.config import Config, load_config
from puya.lib.odoo_client import OdooClient
from puya.lib.rbac import RBACEngine


@dataclass(frozen=True, slots=True)
class Runtime:
    cfg: Config
    rbac: RBACEngine
    client: OdooClient
    audit: AuditLogger
    username: str


def setup() -> Runtime:
    cfg = load_config()
    rbac = RBACEngine()
    client = OdooClient.from_config(cfg)
    user_info = client.execute_kw("res.users", "read", [[client.uid]], {"fields": ["login"]})
    username = user_info[0]["login"] if user_info else str(client.uid)
    audit = AuditLogger(
        user=username,
        role=cfg.role,
        supabase_url=cfg.supabase_url or None,
        supabase_key=cfg.supabase_service_key or None,
    )
    return Runtime(cfg=cfg, rbac=rbac, client=client, audit=audit, username=username)
