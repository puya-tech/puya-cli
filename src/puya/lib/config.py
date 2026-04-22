"""Configuración del CLI.

Resolución por capas (orden de precedencia, gana el más arriba):
  1. Flags de CLI (no implementado todavía)
  2. Variables de entorno (PUYA_*, ODOO_*, SUPABASE_*)
  3. Archivo de usuario `~/.config/puya/config.toml` (futuro)

Multi-entorno: ODOO_ENV indica el entorno (production | staging). Si no
se setea, se infiere del URL.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Config:
    # Odoo (ya con env resolved)
    environment: str
    odoo_url: str
    odoo_db: str
    odoo_login: str
    odoo_api_key: str

    # Role efectivo del agente
    role: str

    # Supabase (para audit + pending actions)
    supabase_url: str
    supabase_service_key: str

    @staticmethod
    def available_environments() -> list[str]:
        """Lista de entornos detectables vía env vars (ODOO_<ENV>_URL)."""
        envs: set[str] = set()
        for key in os.environ:
            if key.startswith("ODOO_") and key.endswith("_URL"):
                env_name = key[len("ODOO_") : -len("_URL")].lower()
                if env_name and env_name not in {"executor"}:
                    envs.add(env_name)
        return sorted(envs)


def _env(*keys: str, default: str = "") -> str:
    """Devuelve el primer env var no vacío de la lista, o default."""
    for k in keys:
        v = os.environ.get(k)
        if v:
            return v
    return default


def load_config() -> Config:
    """Construye la Config a partir del entorno actual.

    Resuelve qué entorno Odoo apuntar según `ODOO_ENV` (`production` |
    `staging` | nombre custom). Si no está, usa `ODOO_URL`/`ODOO_DB`/etc.
    directos (compatible con setup MCP actual).
    """
    env_name = _env("PUYA_ODOO_ENV", "ODOO_ENV", default="")

    if env_name:
        prefix = f"ODOO_{env_name.upper()}_"
        odoo_url = _env(f"{prefix}URL")
        odoo_db = _env(f"{prefix}DB")
        odoo_api_key = _env(f"{prefix}API_KEY")
        # Login puede ser global (mismo user en prod/staging) o por entorno
        odoo_login = _env(f"{prefix}LOGIN", "ODOO_LOGIN")
    else:
        # Modo legacy: ODOO_URL/DB/LOGIN/API_KEY directos
        odoo_url = _env("ODOO_URL")
        odoo_db = _env("ODOO_DB")
        odoo_login = _env("ODOO_LOGIN")
        odoo_api_key = _env("ODOO_API_KEY")
        env_name = _detect_env_from_url(odoo_url)

    role = _env("PUYA_ROLE", "ODOO_ROLE", default="vendedor")

    return Config(
        environment=env_name or "unknown",
        odoo_url=(odoo_url or "").rstrip("/"),
        odoo_db=odoo_db,
        odoo_login=odoo_login,
        odoo_api_key=odoo_api_key,
        role=role,
        supabase_url=_env("SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_URL").rstrip("/"),
        supabase_service_key=_env("SUPABASE_SERVICE_KEY", "SUPABASE_SERVICE_ROLE_KEY"),
    )


def _detect_env_from_url(url: str) -> str:
    if not url:
        return "unknown"
    low = url.lower()
    if ".dev.odoo.com" in low or "-staging-" in low:
        return "staging"
    return "production"
