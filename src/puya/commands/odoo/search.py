"""`puya odoo search <model>` — search_read via puya-chat proxy."""

from __future__ import annotations

from typing import Annotated

import typer

from puya.commands._helpers import EnvOption, handle_api_error, parse_domain, setup_client
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
    env: EnvOption = None,
) -> None:
    """search_read via /api/cli-odoo/search."""
    if limit < 1:
        typer.echo(
            "error: --limit debe ser >= 1 (limit=0 en Odoo devuelve TODOS los records)", err=True
        )
        raise typer.Exit(code=1)

    _, client = setup_client(env=env)

    domain_parsed = parse_domain(domain)
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
            status, body = client.post("/api/cli-odoo/search", json=payload)
        except PuyaApiError as e:
            handle_api_error(e)
            return

    # 202 = read bloqueado por threshold, server creó pending action.
    # Emitimos el body completo (incluye pending_id) y exit 3 para que
    # el agente espere approval — NO podemos devolver `body["records"]`
    # silenciosamente como si fuera resultado vacío.
    if status == 202:
        emit(body, fmt=output)
        raise typer.Exit(code=3)

    records = body.get("records", []) if isinstance(body, dict) else body
    if len(records) == limit:
        from puya.lib.output import emit_hint

        emit_hint(
            "truncated", f"{limit} records devueltos (limit alcanzado) — usá --offset para paginar"
        )
    emit(records, fmt=output)
