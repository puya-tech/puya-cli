"""`puya odoo delete <model> <ids>` — preview de unlink (solo developer)."""

from __future__ import annotations

import json
from typing import Annotated

import typer

from puya.lib.approvals import build_details, needs_approval, notify
from puya.lib.odoo_client import OdooError
from puya.lib.output import emit
from puya.lib.previews import build_delete_preview
from puya.lib.rbac import PermissionDenied
from puya.lib.runtime import setup


def delete_command(
    model: Annotated[str, typer.Argument(help="Modelo Odoo")],
    ids: Annotated[str, typer.Argument(help="IDs separados por coma o JSON list.")],
    reason: Annotated[
        str | None, typer.Option("--reason", "-r", help="Razón (obligatoria en masivos).")
    ] = None,
    output: Annotated[str, typer.Option("--output", "-o")] = "json",
) -> None:
    """Elimina registros (con flujo de aprobación). Operación destructiva."""
    rt = setup()
    massive_threshold = rt.rbac.massive_threshold
    expiry = rt.rbac.pending_expiry_minutes

    try:
        rt.rbac.check_model_access(rt.role, model, "unlink")
    except PermissionDenied as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=1) from e

    try:
        if ids.strip().startswith("["):
            id_list = json.loads(ids)
        else:
            id_list = [int(x.strip()) for x in ids.split(",") if x.strip()]
    except (json.JSONDecodeError, ValueError) as e:
        typer.echo(f"error: ids inválidos: {e}", err=True)
        raise typer.Exit(code=1) from e

    try:
        old_records = rt.client.execute_kw(model, "read", [id_list])
    except OdooError as e:
        typer.echo(f"error leyendo records: {e}", err=True)
        raise typer.Exit(code=2) from e

    is_massive = len(id_list) > massive_threshold
    preview = build_delete_preview(model, old_records)
    requires_approval = needs_approval(rt.rbac, rt.role, is_massive=is_massive)
    status = "approval_required" if requires_approval else "pending"

    pending_id = rt.audit.create_pending(
        action="unlink",
        model=model,
        record_ids=id_list,
        old_values=old_records,
        new_values=None,
        preview=preview,
        is_massive=is_massive,
        record_count=len(id_list),
        details=build_details(rt.cfg, reason=reason),
        expiry_minutes=expiry,
        status=status,
    )

    response: dict = {
        "pending_id": pending_id,
        "model": model,
        "record_count": len(id_list),
        "is_massive": is_massive,
        "preview": preview,
    }

    if requires_approval:
        msg_id, channel = notify(
            rt.cfg,
            pending_id=pending_id,
            user=rt.username,
            role=rt.role,
            action="delete",
            model=model,
            record_count=len(id_list),
            preview=preview,
            reason=reason,
            audit=rt.audit,
        )
        response["status"] = "approval_required"
        response["notified_channel"] = channel
        response["notified_message_id"] = msg_id
        response["instructions"] = f"Solicitud enviada a {channel}. Aprobación humana requerida."
        emit(response, fmt=output)
        raise typer.Exit(code=3)

    response["status"] = "pending"
    response["instructions"] = f"Confirmar con: puya odoo confirm {pending_id}"
    emit(response, fmt=output)
