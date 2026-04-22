"""`puya odoo status` — info de conexión y permisos efectivos."""

from __future__ import annotations

import typer

from puya.lib.output import emit
from puya.lib.runtime import setup


def status_command(
    output: str = typer.Option(
        "table", "--output", "-o", help="Formato de salida: table | json | raw"
    ),
) -> None:
    """Muestra entorno Odoo, role efectivo (de Odoo), conectividad."""
    rt = setup()
    data = {
        "environment": rt.cfg.environment,
        "odoo_url": rt.cfg.odoo_url,
        "odoo_db": rt.cfg.odoo_db,
        "odoo_login": rt.username,
        "uid": rt.client.uid,
        "role": rt.role,
        "role_source": rt.role_source,
        "supabase_configured": bool(rt.cfg.supabase_url and rt.cfg.supabase_service_key),
        "available_envs": rt.cfg.available_environments(),
    }
    emit(data, fmt=output)
