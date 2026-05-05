"""`puya odoo status` — handshake con puya-chat."""

from __future__ import annotations

from typing import Annotated

import typer

from puya.lib.client import PuyaApiError, PuyaClient
from puya.lib.config import load_config, validate_config
from puya.lib.output import emit


def status_command(
    output: Annotated[
        str, typer.Option("--output", "-o", help="Formato: table | json | raw.")
    ] = "json",
) -> None:
    """Devuelve consumer + key + límites efectivos + permisos."""
    cfg = load_config()
    err = validate_config(cfg)
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
