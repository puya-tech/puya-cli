"""`puya odoo fields <model>` — fields_get via puya-chat proxy."""

from __future__ import annotations

from typing import Annotated

import typer

from puya.commands._helpers import EnvOption, handle_api_error, setup_client
from puya.lib.client import PuyaApiError
from puya.lib.output import emit


def fields_command(
    model: Annotated[str, typer.Argument(help="Modelo Odoo")],
    attributes: Annotated[
        str | None,
        typer.Option(
            "--attributes",
            "-a",
            help="Atributos separados por coma. Default: string,type,required,readonly.",
        ),
    ] = None,
    output: Annotated[str, typer.Option("--output", "-o")] = "json",
    env: EnvOption = None,
) -> None:
    """fields_get via /api/cli-odoo/fields."""
    _, client = setup_client(env=env)
    attrs = (
        [a.strip() for a in attributes.split(",")]
        if attributes
        else ["string", "type", "required", "readonly"]
    )

    payload: dict[str, object] = {"model": model, "attributes": attrs}
    with client:
        try:
            _, body = client.post("/api/cli-odoo/fields", json=payload)
        except PuyaApiError as e:
            handle_api_error(e)
            return

    fields = body.get("fields", {}) if isinstance(body, dict) else body
    emit(fields, fmt=output)
