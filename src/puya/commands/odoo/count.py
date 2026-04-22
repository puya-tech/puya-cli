"""`puya odoo count <model>` — search_count contra Odoo."""

from __future__ import annotations

import json
from typing import Annotated

import typer

from puya.lib.odoo_client import OdooError
from puya.lib.output import emit
from puya.lib.rbac import PermissionDenied
from puya.lib.runtime import setup


def count_command(
    model: Annotated[str, typer.Argument(help="Modelo Odoo, ej: 'sale.order'")],
    domain: Annotated[
        str, typer.Option("--domain", "-d", help="Dominio JSON. Default: [].")
    ] = "[]",
    output: Annotated[str, typer.Option("--output", "-o")] = "json",
) -> None:
    """Cuenta registros que matchean un dominio (search_count)."""
    rt = setup()

    try:
        perm = rt.rbac.check_model_access(rt.cfg.role, model, "search_read")
    except PermissionDenied as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=1) from e

    try:
        domain_parsed = json.loads(domain)
    except json.JSONDecodeError as e:
        typer.echo(f"error: --domain no es JSON válido: {e}", err=True)
        raise typer.Exit(code=1) from e

    domain_parsed = rt.rbac.inject_domain(perm, domain_parsed, rt.client.uid)

    try:
        count = rt.client.execute_kw(model, "search_count", [domain_parsed])
    except OdooError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=2) from e

    emit({"count": count}, fmt=output)
