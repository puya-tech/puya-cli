"""`puya odoo create <model> --values <json>` — solicita create con approval."""

from __future__ import annotations

from typing import Annotated

import typer

from puya.commands._helpers import handle_api_error, parse_json, setup_client
from puya.lib.client import PuyaApiError
from puya.lib.output import emit


def create_command(
    model: Annotated[str, typer.Argument(help="Modelo Odoo")],
    values: Annotated[
        str, typer.Option("--values", "-v", help="Valores del nuevo record como JSON.")
    ],
    reason: Annotated[
        str | None,
        typer.Option("--reason", "-r", help="Razón del create"),
    ] = None,
    output: Annotated[str, typer.Option("--output", "-o")] = "json",
) -> None:
    """Crea pending action con approval requerido (exit 3)."""
    _, client = setup_client()
    values_dict = parse_json("values", values)
    if not isinstance(values_dict, dict):
        typer.echo("error: --values debe ser un objeto JSON", err=True)
        raise typer.Exit(code=1)

    payload: dict[str, object] = {"model": model, "values": values_dict}
    if reason:
        payload["reason"] = reason

    with client:
        try:
            status, body = client.post("/api/cli-odoo/create", json=payload)
        except PuyaApiError as e:
            handle_api_error(e)
            return

    emit(body, fmt=output)
    if status == 202:
        raise typer.Exit(code=3)
