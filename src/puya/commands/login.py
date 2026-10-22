"""`puya login` / `puya logout` — entrar con Google en vez de manejar keys.

Las personas entran con su cuenta Google @costasurmat.cl; un admin les
habilita el acceso en puya-chat. Las keys `puya_` (env vars) quedan para
máquinas y, si están, ganan sobre la sesión guardada.
"""

from __future__ import annotations

import os
import time
from typing import Annotated

import httpx
import typer

from puya.commands._helpers import EnvOption
from puya.lib.config import DEFAULT_BASE_URL, VALID_ENVS, _normalize_env
from puya.lib.login import (
    LoginError,
    Session,
    credentials_path,
    delete_session,
    login,
    save_session,
    start_browser,
)


def _base_url() -> str:
    return os.environ.get("PUYA_BASE_URL", "").strip().rstrip("/") or DEFAULT_BASE_URL


def login_command(
    env: EnvOption = None,
    no_browser: Annotated[
        bool,
        typer.Option(
            "--no-browser",
            help="No abre el navegador: muestra la URL para abrirla en otro equipo y pegar la dirección de vuelta.",
        ),
    ] = False,
) -> None:
    """Entra con tu Google y guarda la sesión en este equipo."""
    requested = _normalize_env(env)
    if requested and requested not in VALID_ENVS:
        typer.echo("error: --env debe ser staging o production", err=True)
        raise typer.Exit(code=1)
    base_url = _base_url()

    def show_url(url: str) -> None:
        if no_browser:
            typer.echo(
                f"Abre esta dirección en un navegador y entra con tu Google:\n\n  {url}\n", err=True
            )
        else:
            typer.echo(
                f"Abriendo el navegador para entrar con Google…\n  si no se abre: {url}", err=True
            )
            start_browser(url)

    def ask_pasted_url() -> str:
        typer.echo(
            "Al terminar, el navegador va a una dirección http://127.0.0.1:8976/… que no carga.\n"
            "Cópiala completa desde la barra de direcciones y pégala acá.",
            err=True,
        )
        return typer.prompt("Dirección")

    try:
        access_token, tokens = login(
            base_url,
            requested,
            open_browser=not no_browser,
            show_url=show_url,
            ask_pasted_url=ask_pasted_url,
        )
    except LoginError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=4) from e

    # El servidor dice con qué entorno y consumer quedó la sesión.
    try:
        resp = httpx.get(
            f"{base_url}/api/cli-odoo/status",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30.0,
        )
        status = resp.json()
        target_env = status["api_key"]["target_env"]
        consumer = status.get("consumer", {}).get("name")
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as e:
        typer.echo(f"error: entraste, pero no se pudo confirmar el acceso: {e}", err=True)
        raise typer.Exit(code=5) from e

    save_session(
        Session(
            env=target_env,
            base_url=base_url,
            access_token=access_token,
            refresh_token=tokens["refresh_token"],
            expires_at=time.time() + float(tokens.get("expires_in", 0)),
            consumer=consumer,
        )
    )
    typer.echo(
        f"Listo: {consumer} en {target_env}. Sesión guardada en {credentials_path()}.\n"
        f"  probar:  puya odoo status --env {target_env}",
        err=True,
    )


def logout_command(env: EnvOption = None) -> None:
    """Borra la sesión guardada (de un entorno o de todos)."""
    requested = _normalize_env(env)
    gone = delete_session(requested)
    if gone:
        typer.echo(f"Sesión borrada: {', '.join(gone)}", err=True)
    else:
        typer.echo("No había sesión guardada.", err=True)
