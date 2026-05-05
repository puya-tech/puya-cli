"""Configuración del CLI (post-refactor v1.0).

El CLI no habla con Odoo directamente. Es un wrapper HTTP contra
puya-chat. Solo necesita 2 variables de entorno:

  PUYA_BASE_URL  -- URL del backend (ej: https://puya-chat-interno.vercel.app)
  PUYA_API_KEY   -- API key tipo `puya_xxx` emitida por un admin

La key encapsula entorno (staging | production), permisos por modelo,
custom endpoints habilitados, modo (read_only | full), y rate limit.
Toda la lógica de RBAC + audit + approvals vive server-side en puya-chat.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


DEFAULT_BASE_URL = "https://puya-chat-interno.vercel.app"


@dataclass(frozen=True, slots=True)
class Config:
    base_url: str
    api_key: str


def load_config() -> Config:
    base_url = os.environ.get("PUYA_BASE_URL", "").strip().rstrip("/") or DEFAULT_BASE_URL
    api_key = os.environ.get("PUYA_API_KEY", "").strip()
    return Config(base_url=base_url, api_key=api_key)


def validate_config(cfg: Config) -> str | None:
    """Devuelve None si la config es válida, o un mensaje de error humano."""
    if not cfg.api_key:
        return (
            "PUYA_API_KEY no seteada.\n"
            "  1) Pedile a un admin que cree un slot en /admin/cli-consumers.\n"
            "  2) Loguéate en /cli-account y materializá la key (botón 'Generar mi key').\n"
            "  3) Copiá la key plana (solo aparece UNA vez) y exportala:\n"
            "       export PUYA_API_KEY=puya_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx\n"
            "  4) Verificá: puya odoo status"
        )
    if not cfg.api_key.startswith("puya_"):
        return f"PUYA_API_KEY no parece válida (debería empezar con 'puya_'): {cfg.api_key[:8]}…"
    return None
