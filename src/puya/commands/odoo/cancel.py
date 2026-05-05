"""`puya odoo cancel <pending_id>` — consumer cancela un pending propio."""

from __future__ import annotations

from typing import Annotated

import typer

from puya.commands._helpers import handle_api_error, setup_client
from puya.lib.client import PuyaApiError
from puya.lib.output import emit


def cancel_command(
    pending_id: Annotated[int, typer.Argument(help="ID del pending action")],
    output: Annotated[str, typer.Option("--output", "-o")] = "json",
) -> None:
    """Cancela un pending action propio."""
    _, client = setup_client()
    with client:
        try:
            _, body = client.post(f"/api/cli-odoo/pending/{pending_id}/cancel")
        except PuyaApiError as e:
            handle_api_error(e)
            return

    emit(body, fmt=output)
