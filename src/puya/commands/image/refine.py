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
    output: Annotated[str, typer.Option("--output", "-o")] = "json",
    env: EnvOption = None,
) -> None:
    """Refina (post-proceso IA) una candidata de imagen aún no aprobada.

    Toma la imagen que está pendiente de aprobación en Slack, le aplica la
    instrucción con el motor de IA, y re-postea una tarjeta de aprobación
    nueva. NO escribe en Odoo: el write final de image_1920 lo sigue gateando
    el botón humano de aprobar.
    """
    if not sku and not request_uuid:
        typer.echo("error: pasá --sku o --uuid", err=True)
        raise typer.Exit(code=1)

    cfg = load_config(env_override=env)
    cfg_err = validate_config(cfg, env_override=env)
    if cfg_err:
        typer.echo(f"error: {cfg_err}", err=True)
        raise typer.Exit(code=1)

    payload: dict[str, str] = {"instruction": instruction}
    if sku:
        payload["default_code"] = sku
    if request_uuid:
        payload["request_uuid"] = request_uuid

    client = PuyaClient(cfg, timeout=_REFINE_TIMEOUT_SECONDS)
    with client:
        try:
            _status, body = client.post("/api/image/refine", json=payload)
        except PuyaApiError as e:
            handle_api_error(e)
            return

    emit(body, fmt=output)
