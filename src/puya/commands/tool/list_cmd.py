"""`puya tool list` — descubre tools habilitadas para tu api_key."""

from __future__ import annotations

from typing import Annotated

import typer

from puya.commands._helpers import EnvOption, handle_api_error, setup_client
from puya.lib.client import PuyaApiError
from puya.lib.output import emit


def list_command(
    output: Annotated[
        str, typer.Option("--output", "-o", help="Formato: table | json | raw.")
    ] = "json",
    env: EnvOption = None,
) -> None:
    """Lista las tools custom habilitadas para esta api_key.

    Cada tool incluye `slug`, `description` y `schema` (JSON Schema del body
    POST). Si querés invocar una, usá `puya tool call <slug> --json '...'`.
    """
    _, client = setup_client(env=env)
    with client:
        try:
            _, body = client.get("/api/cli-tools/list")
        except PuyaApiError as e:
            handle_api_error(e)
            return

    tools = body.get("tools", []) if isinstance(body, dict) else body
    emit(tools, fmt=output)
