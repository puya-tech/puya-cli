"""`puya odoo search <model>` — search_read genérico contra Odoo."""

from __future__ import annotations

import json
from typing import Annotated

import typer

from puya.lib.output import emit
from puya.lib.rbac import PermissionDenied
from puya.lib.runtime import setup


def search_command(
    model: Annotated[str, typer.Argument(help="Modelo Odoo, ej: 'purchase.order'")],
    domain: Annotated[
        str,
        typer.Option(
            "--domain",
            "-d",
            help='Dominio Odoo como JSON, ej: \'[["state","=","purchase"]]\'. Default: [].',
        ),
    ] = "[]",
    fields: Annotated[
        str | None,
        typer.Option(
            "--fields",
            "-f",
            help="Campos a leer separados por coma. Default: id, display_name.",
        ),
    ] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max registros.")] = 50,
    offset: Annotated[int, typer.Option("--offset", help="Offset paginación.")] = 0,
    order: Annotated[
        str | None, typer.Option("--order", help="Orden, ej: 'date_order desc'.")
    ] = None,
    output: Annotated[
        str, typer.Option("--output", "-o", help="Formato: table | json | raw.")
    ] = "json",
) -> None:
    """Busca registros en Odoo (search_read).

    Equivalente al tool MCP `odoo_search`. RBAC valida que el rol pueda
    leer el modelo. Devuelve JSON por default (más útil para agentes).
    """
    rt = setup()

    try:
        permission = rt.rbac.check_model_access(rt.role, model, "search_read")
    except PermissionDenied as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=1) from e

    try:
        domain_parsed = json.loads(domain)
    except json.JSONDecodeError as e:
        typer.echo(f"error: --domain no es JSON válido: {e}", err=True)
        raise typer.Exit(code=1) from e

    field_list = [f.strip() for f in fields.split(",")] if fields else ["id", "display_name"]
    field_list = rt.rbac.filter_fields(permission, field_list)

    options: dict[str, object] = {"limit": limit, "offset": offset}
    if order:
        options["order"] = order

    records = rt.client.search_read(model, domain_parsed, field_list, options)
    emit(records, fmt=output)
