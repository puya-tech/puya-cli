"""`puya odoo search <model>` — search_read via puya-chat proxy."""

from __future__ import annotations

from typing import Annotated

import typer

from puya.commands._helpers import handle_api_error, parse_json, setup_client
from puya.lib.client import PuyaApiError
from puya.lib.output import emit


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
    """search_read via /api/cli-odoo/search."""
    _, client = setup_client()

    domain_parsed = parse_json("domain", domain)
    field_list = [f.strip() for f in fields.split(",")] if fields else ["id", "display_name"]

    payload: dict[str, object] = {
        "model": model,
        "domain": domain_parsed,
        "fields": field_list,
        "limit": limit,
        "offset": offset,
    }
    if order:
        payload["order"] = order

    with client:
        try:
            _, body = client.post("/api/cli-odoo/search", json=payload)
        except PuyaApiError as e:
            handle_api_error(e)
            return

    records = body.get("records", []) if isinstance(body, dict) else body
    emit(records, fmt=output)
