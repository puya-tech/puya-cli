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
    _validate_odoo_config(cfg)
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


def _validate_odoo_config(cfg: Config) -> None:
    """Falla rápido con mensaje útil si faltan env vars de Odoo.

    Sin esto, el primer execute_kw revienta con "unsupported XML-RPC protocol"
    o errores crípticos cuando la URL/db/login/api_key están vacíos.
    """
    import sys

    missing = []
    if not cfg.odoo_url:
        missing.append("URL")
    if not cfg.odoo_db:
        missing.append("DB")
    if not cfg.odoo_login:
        missing.append("LOGIN")
    if not cfg.odoo_api_key:
        missing.append("API_KEY")
    if not missing:
        return

    env = cfg.environment.upper() if cfg.environment != "unknown" else None
    prefix = f"ODOO_{env}_" if env else "ODOO_"
    needed = ", ".join(f"{prefix}{m}" for m in missing)

    sys.stderr.write(
        f"error: faltan env vars de Odoo: {needed}\n"
        f"\n"
        f"Setealas y volvé a probar. Ejemplo (staging):\n"
        f"  export ODOO_ENV=staging\n"
        f"  export ODOO_STAGING_URL=https://...dev.odoo.com\n"
        f"  export ODOO_STAGING_DB=...\n"
        f"  export ODOO_LOGIN=tu_email@costasurmat.cl\n"
        f"  export ODOO_STAGING_API_KEY=...\n"
        f"\n"
        f"Estado actual: `puya odoo status`\n"
    )
    sys.exit(1)
