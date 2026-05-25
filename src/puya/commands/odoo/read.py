"""`puya odoo read <model> <ids>` — read via puya-chat proxy."""

from __future__ import annotations

from typing import Annotated

import typer

from puya.commands._helpers import EnvOption, handle_api_error, parse_ids, setup_client
from puya.lib.client import PuyaApiError
from puya.lib.output import emit


def read_command(
    model: Annotated[str, typer.Argument(help="Modelo Odoo")],
    ids: Annotated[str, typer.Argument(help="IDs separados por coma o JSON list")],
    fields: Annotated[
        str | None,
        typer.Option(
            "--fields", "-f", help="Campos separados por coma. Default: id, display_name."
        ),
    ] = None,
    output: Annotated[str, typer.Option("--output", "-o")] = "json",
    env: EnvOption = None,
) -> None:
    """read via /api/cli-odoo/read."""
    _, client = setup_client(env=env)
    id_list = parse_ids(ids)
    field_list = [f.strip() for f in fields.split(",")] if fields else ["id", "display_name"]

    with client:
        try:
            status, body = client.post(
                "/api/cli-odoo/read",
                json={"model": model, "ids": id_list, "fields": field_list},
            )
        except PuyaApiError as e:
            handle_api_error(e)
            return

    if status == 202:
        emit(body, fmt=output)
        raise typer.Exit(code=3)

    records = body.get("records", []) if isinstance(body, dict) else body
    emit(records, fmt=output)
