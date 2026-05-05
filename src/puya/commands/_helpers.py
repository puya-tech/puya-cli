"""Helpers compartidos por los subcomandos."""

from __future__ import annotations

import json
import typer

from puya.lib.client import PuyaApiError, PuyaClient
from puya.lib.config import Config, load_config, validate_config


def setup_client() -> tuple[Config, PuyaClient]:
    """Carga config + valida + abre cliente HTTP. Sale con código 1 si falta config."""
    cfg = load_config()
    err = validate_config(cfg)
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
        return data
    try:
        return [int(x.strip()) for x in s.split(",") if x.strip()]
    except ValueError as e:
        typer.echo(f"error: ids debe ser CSV de enteros o JSON list: {e}", err=True)
        raise typer.Exit(code=1) from e


def handle_api_error(e: PuyaApiError) -> None:
    """Imprime el error a stderr y exit con el código mapeado."""
    typer.echo(f"error: {e}", err=True)
    raise typer.Exit(code=e.exit_code)
