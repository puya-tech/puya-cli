"""`puya update` — reinstala el CLI desde el repo.

Se instala sobre el MISMO intérprete que está corriendo (`sys.executable`),
no sobre el `pip` que aparezca primero en el PATH. En esta máquina conviven
un venv y un pipx con versiones distintas de `puya`, y `pip install` a secas
actualizaba el que no era.
"""

from __future__ import annotations

import subprocess
import sys
from typing import Annotated

import typer

from puya import __version__
from puya.lib.output import emit_hint

REPO_URL = "git+https://github.com/puya-tech/puya-cli.git"


def update_command(
    check: Annotated[
        bool,
        typer.Option(
            "--check",
            help="Solo informa qué se instalaría; no toca nada.",
        ),
    ] = False,
) -> None:
    """Actualiza `puya` a la última versión de `main`."""
    cmd = [sys.executable, "-m", "pip", "install", "--upgrade", REPO_URL]
    # Python 3.11+ en distros con PEP 668 rechaza instalar fuera de un venv
    # sin este flag. En un venv es innecesario pero inofensivo.
    if sys.version_info >= (3, 11):
        cmd.insert(4, "--break-system-packages")

    typer.echo(f"versión actual: {__version__}")
    typer.echo(f"intérprete:     {sys.executable}")
    typer.echo(f"comando:        {' '.join(cmd)}")

    if check:
        return

    typer.echo("")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        typer.echo(
            "\nerror: la instalación falló. Si es un problema de permisos, corré el "
            "comando de arriba a mano.",
            err=True,
        )
        raise typer.Exit(code=result.returncode)

    emit_hint("cli_updated", {"from": __version__})
    typer.echo("\nlisto. Verificá con: puya version")
