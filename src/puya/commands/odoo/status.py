"""`puya odoo status` — info de conexión y permisos."""

from __future__ import annotations

import typer

from puya.lib.config import load_config
from puya.lib.output import emit


def status_command(
    output: str = typer.Option(
        "table", "--output", "-o", help="Formato de salida: table | json | raw"
    ),
) -> None:
    """Muestra el entorno Odoo configurado, el rol y la conectividad."""
    cfg = load_config()
    data = {
        "environment": cfg.environment,
        "odoo_url": cfg.odoo_url,
        "odoo_db": cfg.odoo_db,
        "odoo_login": cfg.odoo_login,
        "role": cfg.role,
        "supabase_configured": bool(cfg.supabase_url and cfg.supabase_service_key),
        "available_envs": cfg.available_environments(),
    }
    emit(data, fmt=output)
