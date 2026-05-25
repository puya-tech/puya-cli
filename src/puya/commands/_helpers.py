"""Helpers compartidos por los subcomandos."""

from __future__ import annotations

import json
from typing import Annotated

import typer

from puya.lib.client import PuyaApiError, PuyaClient
from puya.lib.config import Config, load_config, validate_config

# Anotación reusable: cada subcomando expone --env para elegir staging vs
# production sin tocar las env vars en runtime. Si no se pasa, la
# resolución cae a PUYA_TARGET_ENV (default), keys únicas seteadas, o
# legacy PUYA_API_KEY. Ver `puya.lib.config.load_config` para el orden.
EnvOption = Annotated[
    str | None,
    typer.Option(
        "--env",
        help="Entorno a targetear: staging | production (alias 'prod'). "
        "Override del default PUYA_TARGET_ENV.",
        show_default=False,
    ),
]


# Anotación reusable para mutations (write/create/delete/call). Cuando un
# agente (Puyol vía OpenCode) ejecuta una mutación, pasa su agent_session_id
# para que el backend lo persista en `odoo_pending_actions.details`. Después,
# cuando el admin aprueba/rechaza/expira, puya-chat puede notificar de vuelta
# al canal del agente (DM Discuss, Slack thread, chatter del record).
#
# Si no viene, el flujo igual funciona — solo no hay callback al agente.
SessionIdOption = Annotated[
    str | None,
    typer.Option(
        "--session-id",
        help="UUID del agent_session que dispara este pending (uso interno "
        "de agentes Puyol). Sin esto, no se notifica al agente cuando el "
        "admin aprueba/rechaza en Slack.",
        show_default=False,
    ),
]


def setup_client(env: str | None = None) -> tuple[Config, PuyaClient]:
    """Carga config + valida + abre cliente HTTP.

    `env` es el override de la flag `--env` del subcomando (si vino).
    Sale con código 1 si la config es inválida.
    """
    cfg = load_config(env_override=env)
    err = validate_config(cfg, env_override=env)
    if err:
        typer.echo(f"error: {err}", err=True)
        raise typer.Exit(code=1)
    return cfg, PuyaClient(cfg)


def parse_json(label: str, value: str) -> object:
    try:
        return json.loads(value)
    except json.JSONDecodeError as e:
        typer.echo(f"error: --{label} no es JSON válido: {e}", err=True)
        raise typer.Exit(code=1) from e


def parse_domain(value: str) -> list:
    """Parsea --domain validando que sea una lista Odoo.

    Sin esto un agente puede mandar `-d '"foo"'` (JSON válido, no-list) y
    el server lo trata como dominio vacío silenciosamente → results que no
    matchean la intención. Fallar acá es más útil que dejar pasar.
    """
    parsed = parse_json("domain", value)
    if not isinstance(parsed, list):
        typer.echo(
            f"error: --domain debe ser una lista Odoo (ej: '[]' o '[[\"x\",\"=\",1]]'), "
            f"recibí: {type(parsed).__name__}",
            err=True,
        )
        raise typer.Exit(code=1)
    return parsed


def parse_ids(value: str) -> list[int]:
    """Parsea ids como lista JSON o CSV de enteros."""
    s = value.strip()
    if s.startswith("["):
        try:
            data = json.loads(s)
        except json.JSONDecodeError as e:
            typer.echo(f"error: ids no es JSON válido: {e}", err=True)
            raise typer.Exit(code=1) from e
        if not isinstance(data, list) or not all(isinstance(x, int) for x in data):
            typer.echo("error: ids tiene que ser lista JSON de enteros", err=True)
            raise typer.Exit(code=1)
        result = data
    else:
        try:
            result = [int(x.strip()) for x in s.split(",") if x.strip()]
        except ValueError as e:
            typer.echo(f"error: ids debe ser CSV de enteros o JSON list: {e}", err=True)
            raise typer.Exit(code=1) from e

    if not result:
        typer.echo("error: ids no puede estar vacío — pasá al menos un ID", err=True)
        raise typer.Exit(code=1)
    return result


def handle_api_error(e: PuyaApiError) -> None:
    """Imprime el error a stderr y exit con el código mapeado."""
    typer.echo(f"error: {e}", err=True)
    raise typer.Exit(code=e.exit_code)
