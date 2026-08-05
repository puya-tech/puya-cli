"""`puya odoo status` — handshake con puya-chat."""

from __future__ import annotations

from typing import Annotated

import typer

from puya.commands._helpers import EnvOption
from puya.lib.client import PuyaApiError, PuyaClient
from puya.lib.config import load_config, validate_config
from puya.lib.output import emit


def status_command(
    output: Annotated[
        str, typer.Option("--output", "-o", help="Formato: table | json | raw.")
    ] = "json",
    env: EnvOption = None,
) -> None:
    """Devuelve consumer + key + límites efectivos + permisos."""
    cfg = load_config(env_override=env)
    err = validate_config(cfg, env_override=env)
    if err:
        typer.echo(f"error: {err}", err=True)
        raise typer.Exit(code=1)

    with PuyaClient(cfg) as client:
        try:
            _, body = client.get("/api/cli-odoo/status")
        except PuyaApiError as e:
            typer.echo(f"error: {e}", err=True)
            raise typer.Exit(code=e.exit_code) from e

    emit(body, fmt=output)

    # `custom_endpoints` viene en el payload pero queda sepultado detrás de
    # ~900 modelos, así que en la práctica nadie se entera de las tools que
    # tiene habilitadas. Va a stderr para no tocar el contrato JSON de stdout.
    tools = body.get("custom_endpoints") if isinstance(body, dict) else None
    if tools:
        typer.echo(
            f"\ntools custom habilitadas para esta key: {', '.join(tools)}\n"
            "  detalle:  puya tool list\n"
            "  invocar:  puya tool call <slug> --json '{...}'",
            err=True,
        )
