"""`puya odoo pending` — lista pending actions del consumer logueado."""

from __future__ import annotations

from typing import Annotated

import typer

from puya.commands._helpers import handle_api_error, setup_client
from puya.lib.client import PuyaApiError
from puya.lib.output import emit


def pending_command(
    output: Annotated[str, typer.Option("--output", "-o")] = "json",
) -> None:
    """Devuelve la lista de pendings creados por el consumer."""
    _, client = setup_client()
    with client:
        try:
            _, body = client.get("/api/cli-odoo/pending")
        except PuyaApiError as e:
            handle_api_error(e)
            return

    pendings = body.get("pendings", []) if isinstance(body, dict) else body
    emit(pendings, fmt=output)
