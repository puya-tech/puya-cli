"""`puya odoo call <model> <method>` — invoca método arbitrario via approval."""

from __future__ import annotations

from typing import Annotated

import typer

from puya.commands._helpers import (
    EnvOption,
    SessionIdOption,
    handle_api_error,
    parse_json,
    setup_client,
)
from puya.lib.client import PuyaApiError
from puya.lib.output import emit


def call_command(
    model: Annotated[str, typer.Argument(help="Modelo Odoo")],
    method: Annotated[str, typer.Argument(help="Método a invocar, ej: 'action_confirm'")],
    args: Annotated[
        str, typer.Option("--args", help="Args posicionales JSON, ej: '[[1,2]]'.")
    ] = "[]",
    kwargs: Annotated[
        str, typer.Option("--kwargs", help="Kwargs JSON, ej: '{\"context\":{...}}'.")
    ] = "{}",
    reason: Annotated[str | None, typer.Option("--reason", "-r", help="Razón")] = None,
    output: Annotated[str, typer.Option("--output", "-o")] = "json",
    env: EnvOption = None,
    session_id: SessionIdOption = None,
) -> None:
    """Crea pending action de execute con approval requerido (exit 3).

    Convención: args[0] (si es lista) se considera la lista de ids
    afectados, igual que execute_kw clásico de Odoo.
    """
    _, client = setup_client(env=env)
    args_list = parse_json("args", args)
    kwargs_dict = parse_json("kwargs", kwargs)
    if not isinstance(args_list, list):
        typer.echo("error: --args debe ser JSON array", err=True)
        raise typer.Exit(code=1)
    if not isinstance(kwargs_dict, dict):
        typer.echo("error: --kwargs debe ser JSON object", err=True)
        raise typer.Exit(code=1)

    record_ids: list[int] = []
    if args_list and isinstance(args_list[0], list):
        record_ids = [x for x in args_list[0] if isinstance(x, int)]

    payload: dict[str, object] = {
        "model": model,
        "method": method,
        "ids": record_ids,
        "args": args_list,
        "kwargs": kwargs_dict,
    }
    if reason:
        payload["reason"] = reason
    if session_id:
        payload["session_id"] = session_id

    with client:
        try:
            status, body = client.post("/api/cli-odoo/call", json=payload)
        except PuyaApiError as e:
            handle_api_error(e)
            return

    emit(body, fmt=output)
    if status == 202:
        raise typer.Exit(code=3)
