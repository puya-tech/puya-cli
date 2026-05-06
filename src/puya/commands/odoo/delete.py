"""`puya odoo delete <model> <ids> --reason <txt>` — solicita unlink con approval."""

from __future__ import annotations

from typing import Annotated

import typer

from puya.commands._helpers import EnvOption, handle_api_error, parse_ids, setup_client
from puya.lib.client import PuyaApiError
from puya.lib.output import emit


def delete_command(
    model: Annotated[str, typer.Argument(help="Modelo Odoo")],
    ids: Annotated[str, typer.Argument(help="IDs separados por coma o JSON list")],
    reason: Annotated[
        str,
        typer.Option(
            "--reason", "-r", help="Razón del borrado (obligatoria — borrado es irreversible)."
        ),
    ],
    output: Annotated[str, typer.Option("--output", "-o")] = "json",
    env: EnvOption = None,
) -> None:
    """Crea pending action de unlink con approval requerido (exit 3)."""
    _, client = setup_client(env=env)
    id_list = parse_ids(ids)

    with client:
        try:
            status, body = client.post(
                "/api/cli-odoo/delete",
                json={"model": model, "ids": id_list, "reason": reason},
            )
        except PuyaApiError as e:
            handle_api_error(e)
            return

    emit(body, fmt=output)
    if status == 202:
        raise typer.Exit(code=3)
