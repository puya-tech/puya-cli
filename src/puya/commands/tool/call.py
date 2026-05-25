"""`puya tool call <slug>` — invoca un endpoint custom registrado.

El endpoint vive en `/api/custom/<slug>` del puya-chat proxy. La api_key
tiene que tener el slug habilitado (`puya_cli.api_key_custom_endpoints`),
si no el server responde 403.
"""

from __future__ import annotations

from typing import Annotated

import typer

from puya.commands._helpers import EnvOption, handle_api_error, parse_json, setup_client
from puya.lib.client import PuyaApiError
from puya.lib.output import emit


def call_command(
    slug: Annotated[
        str, typer.Argument(help="Slug del endpoint custom (ej: 'products-keyword-search').")
    ],
    payload: Annotated[
        str,
        typer.Option(
            "--json",
            "-j",
            help='Body JSON del POST (default: {}). Ej: \'{"query":"taladro","limit":10}\'.',
        ),
    ] = "{}",
    output: Annotated[
        str, typer.Option("--output", "-o", help="Formato de respuesta: json | table | raw.")
    ] = "json",
    env: EnvOption = None,
) -> None:
    """Invoca POST /api/custom/<slug> con el body JSON provisto.

    El schema del body lo definís server-side en `custom_endpoints.schema`.
    Para verlo: `puya tool list` (devuelve cada slug con su JSON Schema).
    """
    _, client = setup_client(env=env)

    body_json = parse_json("json", payload)
    if not isinstance(body_json, dict):
        typer.echo("error: --json debe ser un objeto JSON (no array, no scalar)", err=True)
        raise typer.Exit(code=1)

    path = f"/api/custom/{slug}"
    with client:
        try:
            status, response = client.post(path, json=body_json)
        except PuyaApiError as e:
            # 404 sin error body en la respuesta = slug desconocido y el
            # server no nos dio contexto (típicamente Next.js auto-404).
            # Inyectamos el hint del lado cliente para que el agente sepa
            # qué hacer. Si el server eventualmente devuelve `{"error": ...}`
            # con su propio hint, ese mensaje gana y este branch no aplica.
            if e.status == 404 and not _has_error_body(e.body):
                typer.echo(
                    f"error: tool '{slug}' not found. "
                    f"Probá `puya tool list` para ver los slugs habilitados para tu key.",
                    err=True,
                )
                raise typer.Exit(code=1) from e
            handle_api_error(e)
            return

    emit(response, fmt=output)
    # client.request() normaliza 2xx con body.pending_id a 202 (defensa
    # contra endpoints custom que devuelven 200 + body de approval).
    if status == 202:
        raise typer.Exit(code=3)


def _has_error_body(body: object) -> bool:
    """True si el server nos dio un mensaje útil que vale la pena mostrar."""
    return isinstance(body, dict) and bool(body.get("error"))
