"""`puya odoo write <model> <ids> --values <json>` — solicita write con approval."""

from __future__ import annotations

from typing import Annotated

import typer

from puya.commands._helpers import (
    EnvOption,
    SessionIdOption,
    handle_api_error,
    parse_ids,
    parse_json,
    setup_client,
)
from puya.lib.client import PuyaApiError
from puya.lib.output import emit


def write_command(
    model: Annotated[str, typer.Argument(help="Modelo Odoo")],
    ids: Annotated[str, typer.Argument(help="IDs separados por coma o JSON list")],
    values: Annotated[
        str,
        typer.Option(
            "--values",
            "-v",
            help='Valores como JSON, ej: \'{"date_planned":"2026-05-24"}\'.',
        ),
    ],
    reason: Annotated[
        str | None,
        typer.Option("--reason", "-r", help="Razón del cambio"),
    ] = None,
    output: Annotated[str, typer.Option("--output", "-o")] = "json",
    env: EnvOption = None,
    session_id: SessionIdOption = None,
) -> None:
    """Crea pending action con approval requerido (exit 3)."""
    _, client = setup_client(env=env)
    id_list = parse_ids(ids)
    values_dict = parse_json("values", values)
    if not isinstance(values_dict, dict):
        typer.echo("error: --values debe ser un objeto JSON", err=True)
        raise typer.Exit(code=1)

    payload: dict[str, object] = {"model": model, "ids": id_list, "values": values_dict}
    if reason:
        payload["reason"] = reason
    else:
        from puya.lib.output import emit_hint

        emit_hint("no_reason", "sin --reason/-r: el pending quedará sin justificación en audit")
    if session_id:
        payload["session_id"] = session_id

    with client:
        try:
            status, body = client.post("/api/cli-odoo/write", json=payload)
        except PuyaApiError as e:
            handle_api_error(e)
            return

    emit(body, fmt=output)
    if status == 202:
        raise typer.Exit(code=3)
