"""`puya odoo count <model>` — search_count via puya-chat proxy."""

from __future__ import annotations

from typing import Annotated

import typer

from puya.commands._helpers import EnvOption, handle_api_error, parse_domain, setup_client
from puya.lib.client import PuyaApiError
from puya.lib.output import emit


def count_command(
    model: Annotated[str, typer.Argument(help="Modelo Odoo")],
    domain: Annotated[
        str, typer.Option("--domain", "-d", help="Dominio JSON. Default: [].")
    ] = "[]",
    output: Annotated[str, typer.Option("--output", "-o")] = "json",
    env: EnvOption = None,
) -> None:
    """search_count via /api/cli-odoo/count."""
    _, client = setup_client(env=env)
    domain_parsed = parse_domain(domain)

    with client:
        try:
            _, body = client.post(
                "/api/cli-odoo/count",
                json={"model": model, "domain": domain_parsed},
            )
        except PuyaApiError as e:
            handle_api_error(e)
            return

    emit(body, fmt=output)
