"""`puya odoo confirm` — deprecado en v1.0.

En el modelo nuevo no hay self-confirm: las mutaciones siempre van por
approval humano via Slack del admin. Mantenemos el comando como stub
amigable para no romper scripts viejos.
"""

from __future__ import annotations

from typing import Annotated

import typer

from puya.lib.output import emit


def confirm_command(
    pending_id: Annotated[int, typer.Argument(help="ID del pending action")],
    output: Annotated[str, typer.Option("--output", "-o")] = "json",
) -> None:
    """Stub: las aprobaciones se hacen via Slack del admin, no desde el CLI."""
    emit(
        {
            "error": "deprecated",
            "pending_id": pending_id,
            "message": (
                "Self-confirm no existe en este modelo. Las mutaciones se aprueban "
                "via Slack del admin (canal de aprobaciones). Esperá la notificación "
                "de aprobación o rechazo."
            ),
        },
        fmt=output,
    )
    raise typer.Exit(code=1)
