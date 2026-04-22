"""`puya odoo cancel <pending_id>` — cancela una pending action."""

from __future__ import annotations

from typing import Annotated

import typer

from puya.lib.output import emit
from puya.lib.runtime import setup


def cancel_command(
    pending_id: Annotated[int, typer.Argument(help="ID del pending action")],
    output: Annotated[str, typer.Option("--output", "-o")] = "json",
) -> None:
    """Cancela un pending action. Marca como rechazado en audit."""
    rt = setup()

    pending = rt.audit.get_pending(pending_id)
    if not pending:
        typer.echo(f"error: pending {pending_id} no encontrado", err=True)
        raise typer.Exit(code=1)

    if pending["user_login"] != rt.username:
        typer.echo(
            f"error: pending {pending_id} pertenece a {pending['user_login']}, no a {rt.username}",
            err=True,
        )
        raise typer.Exit(code=1)

    if pending["status"] != "pending":
        typer.echo(
            f"error: pending {pending_id} no está en estado 'pending' (status: {pending['status']})",
            err=True,
        )
        raise typer.Exit(code=1)

    rt.audit.cancel_pending(pending_id)
    emit({"cancelled": True, "pending_id": pending_id}, fmt=output)
