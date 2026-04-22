"""`puya odoo call <model> <method>` — invocar método (action_confirm, etc.)."""

from __future__ import annotations

import json
from typing import Annotated

import typer

from puya.lib.approvals import build_details, needs_approval, notify
from puya.lib.output import emit
from puya.lib.previews import build_execute_preview
from puya.lib.runtime import setup


def call_command(
    model: Annotated[str, typer.Argument(help="Modelo Odoo")],
    method: Annotated[str, typer.Argument(help="Método a invocar, ej: 'action_confirm'")],
    args: Annotated[
        str, typer.Option("--args", help="Argumentos posicionales JSON, ej: '[[1,2]]'.")
    ] = "[]",
    kwargs: Annotated[
        str, typer.Option("--kwargs", help="Kwargs JSON, ej: '{\"context\":{...}}'.")
    ] = "{}",
    reason: Annotated[
        str | None, typer.Option("--reason", "-r", help="Razón (obligatoria en masivos).")
    ] = None,
    output: Annotated[str, typer.Option("--output", "-o")] = "json",
) -> None:
    """Ejecuta un método de modelo (con preview/approval)."""
    rt = setup()
    massive_threshold = rt.rbac.massive_threshold
    expiry = rt.rbac.pending_expiry_minutes

    if not rt.rbac.check_method_access(rt.role, model, method):
        typer.echo(
            f"error: método '{method}' en '{model}' no permitido para role '{rt.role}'",
            err=True,
        )
        raise typer.Exit(code=1)

    try:
        args_list = json.loads(args)
        kwargs_dict = json.loads(kwargs)
    except json.JSONDecodeError as e:
        typer.echo(f"error: --args/--kwargs JSON inválido: {e}", err=True)
        raise typer.Exit(code=1) from e

    record_ids = args_list[0] if args_list and isinstance(args_list[0], list) else []
    is_massive = len(record_ids) > massive_threshold
    preview = build_execute_preview(model, method, record_ids)
    requires_approval = needs_approval(rt.rbac, rt.role, is_massive=is_massive)
    status = "approval_required" if requires_approval else "pending"

    pending_id = rt.audit.create_pending(
        action="execute",
        model=model,
        record_ids=record_ids,
        old_values=None,
        new_values={"method": method, "args": args_list, "kwargs": kwargs_dict},
        preview=preview,
        is_massive=is_massive,
        record_count=len(record_ids),
        details=build_details(rt.cfg, method=method, reason=reason),
        expiry_minutes=expiry,
        status=status,
    )

    response: dict = {
        "pending_id": pending_id,
        "model": model,
        "method": method,
        "record_count": len(record_ids),
        "is_massive": is_massive,
        "preview": preview,
    }

    if requires_approval:
        msg_id, channel = notify(
            rt.cfg,
            pending_id=pending_id,
            user=rt.username,
            role=rt.role,
            action=f"execute:{method}",
            model=model,
            record_count=len(record_ids),
            preview=preview,
            reason=reason,
            audit=rt.audit,
        )
        response["status"] = "approval_required"
        response["notified_channel"] = channel
        response["notified_message_id"] = msg_id
        emit(response, fmt=output)
        raise typer.Exit(code=3)

    response["status"] = "pending"
    response["instructions"] = f"Confirmar con: puya odoo confirm {pending_id}"
    emit(response, fmt=output)
