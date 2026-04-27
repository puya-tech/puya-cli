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
    role: str  # role efectivo (Odoo source of truth, env var puede override)
    role_source: str  # "odoo" | "env_override" | "default"


def setup() -> Runtime:
    cfg = load_config()
    _validate_odoo_config(cfg)
    rbac = RBACEngine()
    client = OdooClient.from_config(cfg)

    user_info = client.execute_kw(
        "res.users", "read", [[client.uid]], {"fields": ["login", "x_mcp_role"]}
    )
    username = user_info[0]["login"] if user_info else str(client.uid)
    odoo_role = user_info[0].get("x_mcp_role") if user_info else None

    # Resolver role efectivo:
    # 1) Si PUYA_ROLE/ODOO_ROLE env var está seteado explícito → override (útil en CI/scripts)
    # 2) Si Odoo tiene x_mcp_role asignado al user → ese (source of truth)
    # 3) Default: vendedor (más conservador)
    env_role_override = _env_role_override()
    if env_role_override:
        role, role_source = env_role_override, "env_override"
    elif odoo_role:
        role, role_source = odoo_role, "odoo"
    else:
        role, role_source = "vendedor", "default"

    audit = AuditLogger(
        user=username,
        role=role,
        supabase_url=cfg.supabase_url or None,
        supabase_key=cfg.supabase_service_key or None,
        puya_chat_url=cfg.puya_chat_url or None,
        odoo_env=cfg.environment if cfg.environment != "unknown" else None,
        odoo_login=cfg.odoo_login or None,
        odoo_api_key=cfg.odoo_api_key or None,
    )
    return Runtime(
        cfg=cfg,
        rbac=rbac,
        client=client,
        audit=audit,
        username=username,
        role=role,
        role_source=role_source,
    )


def _env_role_override() -> str | None:
    """Devuelve el role del env var SI fue seteado explícitamente.

    No considera el default de load_config() (que pone "vendedor"); solo
    si el usuario lo seteó realmente. Si no, devolvemos None y dejamos
    que setup() use Odoo como source of truth.
    """
    import os

    for key in ("PUYA_ROLE", "ODOO_ROLE"):
        v = os.environ.get(key)
        if v:
            return v
    return None


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
