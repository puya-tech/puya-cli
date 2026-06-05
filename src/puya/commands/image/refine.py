"""`puya image refine` — refina una imagen de producto pendiente vía puya-chat."""

from __future__ import annotations

from typing import Annotated

import typer

from puya.commands._helpers import EnvOption, handle_api_error
from puya.lib.client import PuyaApiError, PuyaClient
from puya.lib.config import load_config, validate_config
from puya.lib.output import emit

# Gemini tarda varios segundos en regenerar la imagen; el timeout default del
# CLI es muy corto para esto. Damos margen explícito en este comando.
_REFINE_TIMEOUT_SECONDS = 90.0


def refine_command(
    instruction: Annotated[
        str,
        typer.Argument(
            help="Ajuste a aplicar sobre la imagen pendiente. "
            "Ej: 'saca el óxido y acerca un poco el producto'."
        ),
    ],
    sku: Annotated[
        str | None,
        typer.Option(
            "--sku",
            help="SKU (default_code) del producto. Refina su imagen pendiente más reciente.",
        ),
    ] = None,
    request_uuid: Annotated[
        str | None,
        typer.Option(
            "--uuid",
            help="request_uuid de la solicitud pendiente (alternativa a --sku).",
        ),
    ] = None,
    product_id: Annotated[
        str | None,
        typer.Option(
            "--product-id",
            help="ID del producto/record (ej. desde el chatter de Odoo). Refina la "
            "imagen ACTUAL del producto (image_1920), no una candidata pendiente.",
        ),
    ] = None,
    output: Annotated[str, typer.Option("--output", "-o")] = "json",
    env: EnvOption = None,
) -> None:
    """Refina (post-proceso IA) una imagen de producto.

    Dos modos según el origen:
    - --sku / --uuid: refina una candidata PENDIENTE de aprobación (flujo Slack).
    - --product-id: refina la imagen ACTUAL del producto en Odoo (flujo chatter).

    En ambos casos NO escribe en Odoo: re-postea una tarjeta de aprobación en
    Slack y el write final de image_1920 lo gatea el botón humano.
    """
    if not sku and not request_uuid and not product_id:
        typer.echo("error: pasá --sku, --uuid o --product-id", err=True)
        raise typer.Exit(code=1)

    cfg = load_config(env_override=env)
    cfg_err = validate_config(cfg, env_override=env)
    if cfg_err:
        typer.echo(f"error: {cfg_err}", err=True)
        raise typer.Exit(code=1)

    payload: dict[str, object] = {"instruction": instruction}
    if product_id:
        # Refinar la imagen ACTUAL del producto (chatter): endpoint distinto.
        try:
            payload["product_id"] = int(product_id)
        except ValueError:
            typer.echo("error: --product-id debe ser un entero", err=True)
            raise typer.Exit(code=1) from None
        path = "/api/image/refine-product"
    else:
        if sku:
            payload["default_code"] = sku
        if request_uuid:
            payload["request_uuid"] = request_uuid
        path = "/api/image/refine"

    client = PuyaClient(cfg, timeout=_REFINE_TIMEOUT_SECONDS)
    with client:
        try:
            _status, body = client.post(path, json=payload)
        except PuyaApiError as e:
            handle_api_error(e)
            return

    emit(body, fmt=output)
