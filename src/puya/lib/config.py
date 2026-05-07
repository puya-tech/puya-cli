"""Configuración del CLI (multi-env desde v1.1.0).

El CLI no habla con Odoo directamente. Es un wrapper HTTP contra
puya-chat. La resolución de env vars permite operar contra staging y
producción desde un mismo proceso, eligiendo la key correcta según
la flag `--env` o el default `PUYA_TARGET_ENV`.

Env vars:
  PUYA_BASE_URL          URL del backend (ej: https://puya-chat-interno.vercel.app).
  PUYA_API_KEY_STAGING   API key con target_env=staging.
  PUYA_API_KEY_PROD      API key con target_env=production.
  PUYA_TARGET_ENV        Default cuando no se pasa --env. Valores: staging | production.
  PUYA_API_KEY           Legacy (single-env). Si las nuevas no están seteadas, se usa.

Cada API key encapsula entorno (staging | production), permisos por
modelo, custom endpoints habilitados, modo (read_only | full), y rate
limit. Toda la lógica de RBAC + audit + approvals vive server-side en
puya-chat. El CLI nunca decide permisos.

Resolución de la key efectiva (en orden):
  1. Si `env_override` (de --env) viene seteado:
       - usa PUYA_API_KEY_<ENV>; si no existe, error claro.
  2. Si PUYA_TARGET_ENV está seteada:
       - mismo lookup que 1.
  3. Si solo una de PUYA_API_KEY_STAGING / PUYA_API_KEY_PROD está seteada:
       - usa esa (sin ambigüedad).
  4. Si PUYA_API_KEY (legacy) está seteada:
       - usa esa, target_env queda None (se infiere server-side).
  5. Si nada de lo anterior:
       - error con instrucciones de setup.

Si STAGING y PROD están seteadas pero falta default (--env y PUYA_TARGET_ENV
ausentes y PUYA_API_KEY ausente), se exige especificar --env.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


DEFAULT_BASE_URL = "https://puya-chat-interno.vercel.app"
VALID_ENVS = ("staging", "production")
ENV_TO_VAR = {
    "staging": "PUYA_API_KEY_STAGING",
    "production": "PUYA_API_KEY_PROD",
}


@dataclass(frozen=True, slots=True)
class Config:
    base_url: str
    api_key: str
    # target_env: cuando se eligió por --env / PUYA_TARGET_ENV / única env disponible.
    # None cuando solo se usó PUYA_API_KEY legacy (server-side resuelve el env).
    target_env: str | None


def _normalize_env(value: str | None) -> str | None:
    """Normaliza variantes razonables (case-insensitive, alias 'prod')."""
    if not value:
        return None
    v = value.strip().lower()
    if v in ("prod", "production"):
        return "production"
    if v == "staging":
        return "staging"
    return v  # devuelve tal cual para que validate_config lo rechace con mensaje claro


def load_config(env_override: str | None = None) -> Config:
    """Resuelve la config efectiva.

    `env_override` viene de la flag --env. Si está, gana sobre PUYA_TARGET_ENV.
    """
    base_url = os.environ.get("PUYA_BASE_URL", "").strip().rstrip("/") or DEFAULT_BASE_URL

    staging_key = os.environ.get("PUYA_API_KEY_STAGING", "").strip()
    prod_key = os.environ.get("PUYA_API_KEY_PROD", "").strip()
    legacy_key = os.environ.get("PUYA_API_KEY", "").strip()
    default_env = _normalize_env(os.environ.get("PUYA_TARGET_ENV"))
    requested = _normalize_env(env_override) or default_env

    target_env: str | None = None
    api_key: str = ""

    if requested in VALID_ENVS:
        target_env = requested
        api_key = staging_key if requested == "staging" else prod_key
    elif staging_key and not prod_key:
        target_env, api_key = "staging", staging_key
    elif prod_key and not staging_key:
        target_env, api_key = "production", prod_key
    elif legacy_key:
        target_env, api_key = None, legacy_key
    elif staging_key and prod_key:
        # Ambas seteadas pero sin default — devolver vacío para que
        # validate_config emita un error pidiendo --env / PUYA_TARGET_ENV.
        target_env, api_key = None, ""

    return Config(base_url=base_url, api_key=api_key, target_env=target_env)


def validate_config(cfg: Config, env_override: str | None = None) -> str | None:
    """Devuelve None si la config es válida, o un mensaje de error humano.

    `env_override` permite mensajes más útiles cuando el user pidió un env
    explícito y la key correspondiente no está.
    """
    requested = _normalize_env(env_override) or _normalize_env(os.environ.get("PUYA_TARGET_ENV"))

    if requested and requested not in VALID_ENVS:
        return (
            f"valor inválido para env: '{requested}'. "
            f"Permitidos: 'staging' o 'production' (alias 'prod')."
        )

    staging_key = os.environ.get("PUYA_API_KEY_STAGING", "").strip()
    prod_key = os.environ.get("PUYA_API_KEY_PROD", "").strip()

    if not cfg.api_key:
        if requested in VALID_ENVS:
            var = ENV_TO_VAR[requested]
            return (
                f"{var} no seteada — no podés operar contra '{requested}' sin esa key.\n"
                f"  Setealá con la key emitida en /cli-account, o pasá --env apuntando "
                f"al entorno cuya key sí tengas."
            )
        if staging_key and prod_key:
            return (
                "PUYA_API_KEY_STAGING y PUYA_API_KEY_PROD están seteadas pero no hay "
                "entorno default. Pasá --env staging|production en el comando, "
                "o exportá PUYA_TARGET_ENV=<staging|production>."
            )
        return (
            "API key no seteada. Configurala así:\n"
            "  Multi-env (recomendado para agentes Puyol):\n"
            "    export PUYA_API_KEY_STAGING=puya_xxx\n"
            "    export PUYA_API_KEY_PROD=puya_yyy\n"
            "    export PUYA_TARGET_ENV=staging        # default cuando no se pasa --env\n"
            "  Single-env (legacy):\n"
            "    export PUYA_API_KEY=puya_xxx\n"
            "  Las keys se materializan desde /cli-account (botón 'Generar mi key').\n"
            "  Si las perdés, no se recuperan — pediselo a un admin\n"
            "  (nlewin@costasurmat.cl o dducci@costasurmat.cl) un slot nuevo.\n"
            "  Verificá con: puya odoo status"
        )

    if not cfg.api_key.startswith("puya_"):
        return (
            f"API key no parece válida (debería empezar con 'puya_'): {cfg.api_key[:8]}…\n"
            f"  Probable mismatch entre PUYA_API_KEY_* y --env / PUYA_TARGET_ENV. "
            f"Verificá las env vars."
        )

    return None
