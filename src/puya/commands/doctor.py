"""`puya doctor` — diagnóstico del setup local.

Pensado para correr antes de pegarle a la red por primera vez (o cuando
algo falla y querés saber por qué). Reporta:

  - versiones (cli, python, OS)
  - qué env vars PUYA_* están seteadas (keys redactadas)
  - qué env / qué key elegiría el CLI con esa config
  - conectividad contra PUYA_BASE_URL (HEAD /)  ← opcional, `--no-network`

Útil tanto para humanos (output text con Rich) como para agentes (output
json estable, mismo schema).

Exit codes:
  0 = nada raro
  1 = al menos un issue (config inválida o base_url inalcanzable)
"""

from __future__ import annotations

import os
import platform
import sys
from typing import Annotated

import httpx
import typer
from rich.console import Console

from puya import __version__
from puya.lib.config import (
    DEFAULT_BASE_URL,
    ENV_TO_VAR,
    load_config,
    validate_config,
)
from puya.lib.output import emit

ENV_VAR_NAMES = (
    "PUYA_BASE_URL",
    "PUYA_API_KEY_STAGING",
    "PUYA_API_KEY_PROD",
    "PUYA_API_KEY",
    "PUYA_TARGET_ENV",
)


def _redact(value: str) -> str:
    """Redacta una API key dejando prefijo + 4 últimos chars."""
    if not value:
        return ""
    if len(value) <= 12:
        return "***"
    if value.startswith("puya_"):
        return f"{value[:9]}…{value[-4:]}"
    return f"{value[:4]}…{value[-4:]}"


def _gather_env_vars() -> dict:
    out: dict[str, dict] = {}
    for name in ENV_VAR_NAMES:
        raw = os.environ.get(name, "").strip()
        if not raw:
            out[name] = {"set": False}
        elif "API_KEY" in name:
            out[name] = {"set": True, "value_redacted": _redact(raw)}
        else:
            out[name] = {"set": True, "value": raw}
    return out


def _resolve_config(env_vars: dict) -> dict:
    cfg = load_config(env_override=None)
    err = validate_config(cfg, env_override=None)

    source: str | None = None
    if cfg.api_key:
        if cfg.target_env in ENV_TO_VAR:
            source = ENV_TO_VAR[cfg.target_env]
        elif env_vars.get("PUYA_API_KEY", {}).get("set"):
            source = "PUYA_API_KEY"

    return {
        "base_url": cfg.base_url,
        "target_env": cfg.target_env,
        "api_key_source": source,
        "error": err,
    }


def _check_connectivity(base_url: str, *, timeout: float = 5.0) -> dict:
    try:
        # HEAD a la raíz: Vercel devuelve 200/308/etc. Cualquier respuesta
        # HTTP cuenta como "alcanzable", no nos importa el status puntual.
        resp = httpx.head(base_url, timeout=timeout, follow_redirects=False)
        return {
            "checked": True,
            "base_url": base_url,
            "reachable": True,
            "status": resp.status_code,
            "error": None,
        }
    except httpx.RequestError as e:
        return {
            "checked": True,
            "base_url": base_url,
            "reachable": False,
            "status": None,
            "error": f"{type(e).__name__}: {e}",
        }


def _gather(*, no_network: bool) -> dict:
    env_vars = _gather_env_vars()
    resolution = _resolve_config(env_vars)
    connectivity = (
        {
            "checked": False,
            "base_url": resolution["base_url"],
            "reachable": None,
            "status": None,
            "error": None,
        }
        if no_network
        else _check_connectivity(resolution["base_url"])
    )

    issues: list[str] = []
    if resolution["error"]:
        issues.append(f"config: {resolution['error'].splitlines()[0]}")
    if connectivity["checked"] and not connectivity["reachable"]:
        issues.append(f"network: no se pudo conectar a {connectivity['base_url']}")

    return {
        "ok": not issues,
        "versions": {
            "cli": __version__,
            "python": platform.python_version(),
            "platform": f"{platform.system()}-{platform.release()}-{platform.machine()}",
        },
        "env_vars": env_vars,
        "resolution": resolution,
        "connectivity": connectivity,
        "issues": issues,
    }


def _render_text(report: dict) -> None:
    console = Console(stderr=False)
    ok = report["ok"]

    console.print(
        f"[bold]puya doctor[/bold]  {'[green]✓ OK[/green]' if ok else '[red]✗ issues[/red]'}"
    )
    console.print()

    v = report["versions"]
    console.print(
        f"[bold]versions[/bold]   cli={v['cli']}  python={v['python']}  platform={v['platform']}"
    )
    console.print()

    console.print("[bold]env vars[/bold]")
    for name, info in report["env_vars"].items():
        if not info["set"]:
            console.print(f"  [dim]{name:24} (no set)[/dim]")
        elif "value_redacted" in info:
            console.print(f"  {name:24} [cyan]{info['value_redacted']}[/cyan]")
        else:
            console.print(f"  {name:24} [cyan]{info['value']}[/cyan]")
    console.print()

    r = report["resolution"]
    console.print("[bold]resolution[/bold]")
    console.print(
        f"  base_url       [cyan]{r['base_url']}[/cyan]"
        + ("  [dim](default)[/dim]" if r["base_url"] == DEFAULT_BASE_URL else "")
    )
    console.print(f"  target_env     [cyan]{r['target_env'] or '(unresolved)'}[/cyan]")
    console.print(f"  api_key_source [cyan]{r['api_key_source'] or '(none)'}[/cyan]")
    if r["error"]:
        console.print(f"  [red]error[/red]          {r['error'].splitlines()[0]}")
    console.print()

    c = report["connectivity"]
    console.print("[bold]connectivity[/bold]")
    if not c["checked"]:
        console.print("  [dim](skipped — --no-network)[/dim]")
    elif c["reachable"]:
        console.print(f"  [green]✓[/green] {c['base_url']} responde (HTTP {c['status']})")
    else:
        console.print(f"  [red]✗[/red] {c['base_url']} no responde: {c['error']}")
    console.print()

    if report["issues"]:
        console.print("[bold red]issues[/bold red]")
        for i in report["issues"]:
            console.print(f"  • {i}")


def doctor_command(
    no_network: Annotated[
        bool,
        typer.Option("--no-network", "-n", help="Saltar chequeo de conectividad."),
    ] = False,
    output: Annotated[
        str,
        typer.Option("--output", "-o", help="text (humano) | json (agente)."),
    ] = "text",
) -> None:
    """Diagnostica el setup local sin operar contra el proxy."""
    report = _gather(no_network=no_network)
    if output == "json":
        emit(report, fmt="json")
    else:
        _render_text(report)
    if not report["ok"]:
        sys.exit(1)
