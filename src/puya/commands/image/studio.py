"""`puya image studio` — recrea la imagen actual de un producto como foto de estudio."""

from __future__ import annotations

from typing import Annotated

import typer

from puya.commands._helpers import EnvOption, handle_api_error
from puya.lib.client import PuyaApiError, PuyaClient
from puya.lib.config import load_config, validate_config
from puya.lib.output import emit

_TIMEOUT_SECONDS = 90.0


def studio_command(
    product_id: Annotated[
        str,
        typer.Option(
            "--product-id",
            help="ID del producto/record (ej. desde el chatter de Odoo). Recrea su "
            "imagen ACTUAL como foto de estudio (fondo blanco + logo Puya).",
        ),
    ],
    output: Annotated[str, typer.Option("--output", "-o")] = "json",
    env: EnvOption = None,
) -> None:
    """Recrea la imagen actual de un producto como foto de estudio (fondo blanco + logo).

    Toma la image_1920 actual del producto y la re-genera limpia con IA, y postea
    una tarjeta de aprobación en Slack. NO escribe en Odoo: el write final lo
    gatea el botón humano de aprobar. Es el motor de GENERACIÓN (recrea), distinto
    de `puya image refine` (que aplica un ajuste puntual).
    """
    cfg = load_config(env_override=env)
    cfg_err = validate_config(cfg, env_override=env)
    if cfg_err:
        typer.echo(f"error: {cfg_err}", err=True)
        raise typer.Exit(code=1)

    try:
        pid = int(product_id)
    except ValueError:
        typer.echo("error: --product-id debe ser un entero", err=True)
        raise typer.Exit(code=1) from None

    payload: dict[str, object] = {"mode": "studio", "product_id": pid}
    client = PuyaClient(cfg, timeout=_TIMEOUT_SECONDS)
    with client:
        try:
            _status, body = client.post("/api/image/refine-product", json=payload)
        except PuyaApiError as e:
            handle_api_error(e)
            return

    emit(body, fmt=output)
