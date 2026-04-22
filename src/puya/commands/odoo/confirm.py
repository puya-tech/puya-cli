"""`puya odoo confirm <pending_id>` — ejecuta una pending action aprobada.

Solo aplica a pendings en estado `pending` (sin always_approve). Los que
están en `approval_required` NO se pueden confirmar desde acá — los
resuelve el approval-execute workflow tras click en Slack/Odoo.
"""

from __future__ import annotations

import time
from typing import Annotated

import typer

from puya.lib.odoo_client import OdooError
from puya.lib.output import emit
from puya.lib.runtime import setup


def confirm_command(
    pending_id: Annotated[int, typer.Argument(help="ID del pending action")],
    output: Annotated[str, typer.Option("--output", "-o")] = "json",
) -> None:
    """Ejecuta el pending action contra Odoo, registra audit, marca confirmado."""
    rt = setup()

    pending = rt.audit.get_pending(pending_id)
    if not pending:
        typer.echo(f"error: pending {pending_id} no encontrado", err=True)
        raise typer.Exit(code=1)

    if pending["status"] == "approval_required":
        emit(
            {
                "error": "approval_required",
                "pending_id": pending_id,
                "instructions": "Esta acción requiere aprobación humana via Slack/Odoo.",
            },
            fmt=output,
        )
        raise typer.Exit(code=3)

    if pending["status"] != "pending":
        typer.echo(
            f"error: pending {pending_id} no está en estado 'pending' (status: {pending['status']})",
            err=True,
        )
        raise typer.Exit(code=1)

    if pending["user_login"] != rt.username:
        typer.echo(
            f"error: pending {pending_id} pertenece a {pending['user_login']}, no a {rt.username}",
            err=True,
        )
        raise typer.Exit(code=1)

    action = pending["action"]
    model = pending["model"]
    record_ids = pending.get("record_ids") or []
    new_values = pending.get("new_values")
    old_values = pending.get("old_values")

    t0 = time.time()
    try:
        if action == "write":
            result = rt.client.execute_kw(model, "write", [record_ids, new_values])
            duration = (time.time() - t0) * 1000
            audit_id = rt.audit.log_mutation(
                "write",
                model,
                record_ids,
                old_values=old_values,
                new_values=new_values,
                details=pending.get("details"),
                duration_ms=duration,
            )
            rt.audit.confirm_pending(pending_id, audit_id)
            emit(
                {
                    "success": result,
                    "ids": record_ids,
                    "audit_id": audit_id,
                    "pending_id": pending_id,
                },
                fmt=output,
            )
        elif action == "create":
            new_id = rt.client.execute_kw(model, "create", [new_values])
            duration = (time.time() - t0) * 1000
            audit_id = rt.audit.log_mutation(
                "create",
                model,
                [new_id],
                old_values=None,
                new_values=new_values,
                duration_ms=duration,
            )
            rt.audit.confirm_pending(pending_id, audit_id)
            emit({"id": new_id, "audit_id": audit_id, "pending_id": pending_id}, fmt=output)
        elif action == "execute":
            method = new_values["method"]
            args = new_values.get("args", [])
            kwargs = new_values.get("kwargs")
            result = rt.client.execute_kw(model, method, args, kwargs)
            duration = (time.time() - t0) * 1000
            audit_id = rt.audit.log_mutation(
                "execute",
                model,
                record_ids,
                old_values=None,
                new_values=new_values,
                details={"method": method},
                duration_ms=duration,
            )
            rt.audit.confirm_pending(pending_id, audit_id)
            emit(
                {"result": result, "audit_id": audit_id, "pending_id": pending_id},
                fmt=output,
            )
        elif action == "unlink":
            result = rt.client.execute_kw(model, "unlink", [record_ids])
            duration = (time.time() - t0) * 1000
            audit_id = rt.audit.log_mutation(
                "unlink",
                model,
                record_ids,
                old_values=old_values,
                new_values=None,
                duration_ms=duration,
            )
            rt.audit.confirm_pending(pending_id, audit_id)
            emit(
                {"success": result, "deleted_ids": record_ids, "audit_id": audit_id},
                fmt=output,
            )
        else:
            typer.echo(f"error: action desconocida: {action}", err=True)
            raise typer.Exit(code=1)
    except OdooError as e:
        typer.echo(f"error Odoo: {e}", err=True)
        raise typer.Exit(code=2) from e
