"""`puya account` — mostrar info del consumer + slots desde la terminal.

Hoy si querés ver tus slots tenés que abrir `/cli-account` en el browser.
Este comando lo hace desde la terminal — útil para agentes, scripts, y
para devs que están en una sesión SSH sin GUI.

Auth: usa la api_key actual (cualquier env vale — el endpoint server-side
deriva el consumer de la key, no del env).

Endpoint: GET /api/cli-account/me (devuelve consumer + array de slots).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from puya.commands._helpers import EnvOption
from puya.lib.client import PuyaApiError, PuyaClient
from puya.lib.config import load_config, validate_config
from puya.lib.output import emit


def _fmt_ago(iso: str | None) -> str:
    if not iso:
        return "never"
    try:
        # Acepta '...+00:00' y 'Z'
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return iso[:19]
    delta = datetime.now(timezone.utc) - dt
    s = int(delta.total_seconds())
    if s < 60:
        return f"{s}s ago"
    if s < 3600:
        return f"{s // 60}m ago"
    if s < 86400:
        return f"{s // 3600}h ago"
    return f"{s // 86400}d ago"


def _state_label(active: bool, generated_at: str | None) -> str:
    if not active:
        return "revoked"
    if not generated_at:
        return "pending"
    return "active"


def _render_table(data: dict[str, Any]) -> None:
    console = Console()
    c = data["consumer"]
    console.print(
        f"[bold]Consumer:[/bold] {c['email']}  "
        f"([cyan]{c.get('name') or '—'}[/cyan] · {c.get('kind') or '—'})"
    )
    console.print()

    keys = data.get("api_keys", [])
    if not keys:
        console.print("[dim]No tenés slots todavía. Pedile a un admin que te cree uno.[/dim]")
        return

    table = Table(show_lines=False, expand=False)
    table.add_column("label", style="bold")
    table.add_column("env")
    table.add_column("mode")
    table.add_column("state")
    table.add_column("prefix", style="dim")
    table.add_column("models", justify="right")
    table.add_column("custom eps", justify="right")
    table.add_column("last used")
    for k in keys:
        env = k.get("target_env") or "—"
        mode = k.get("cli_mode") or "—"
        state = _state_label(bool(k.get("active")), k.get("generated_at"))
        env_color = "red" if env == "production" else "yellow"
        state_color = {"active": "green", "pending": "yellow", "revoked": "dim"}.get(
            state, "white"
        )
        table.add_row(
            k.get("label", ""),
            f"[{env_color}]{env}[/{env_color}]",
            mode,
            f"[{state_color}]{state}[/{state_color}]",
            (k.get("key_prefix") or "—") + ("…" if k.get("key_prefix") else ""),
            str(k.get("models_count", 0)),
            str(k.get("custom_endpoints_count", 0)),
            _fmt_ago(k.get("last_used_at")),
        )
    console.print(table)


def account_command(
    output: Annotated[
        str,
        typer.Option(
            "--output",
            "-o",
            help="Formato: table (default, humano) | json | raw.",
        ),
    ] = "table",
    env: EnvOption = None,
) -> None:
    """Muestra consumer info + todos los slots del consumer.

    No requiere --env (el endpoint funciona con cualquier key del consumer),
    pero si pasás --env el CLI lo usa para elegir cuál key autenticar.
    """
    cfg = load_config(env_override=env)
    err = validate_config(cfg, env_override=env)
    if err:
        typer.echo(f"error: {err}", err=True)
        raise typer.Exit(code=1)

    with PuyaClient(cfg) as client:
        try:
            _, body = client.get("/api/cli-account/me")
        except PuyaApiError as e:
            typer.echo(f"error: {e}", err=True)
            raise typer.Exit(code=e.exit_code) from e

    if output.lower() == "table":
        _render_table(body)
    else:
        emit(body, fmt=output)
