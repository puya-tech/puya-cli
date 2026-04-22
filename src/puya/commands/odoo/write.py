"""`puya odoo write <model> <ids> --values <json>` — preview de update.

NO ejecuta directamente. Crea un pending_action y devuelve preview +
pending_id. Si el role tiene `always_approve` o el write es masivo,
notifica a Slack y deja el pending en estado `approval_required`
(solo aprobación humana lo destraba).

Si NO necesita approval, queda en estado `pending` listo para
`puya odoo confirm <pending_id>`.
"""

from __future__ import annotations

import json
from typing import Annotated

import typer

from puya.lib.approvals import build_details, needs_approval, notify
from puya.lib.odoo_client import OdooError
from puya.lib.output import emit
from puya.lib.previews import build_write_preview
from puya.lib.rbac import PermissionDenied
from puya.lib.runtime import setup


def write_command(
    model: Annotated[str, typer.Argument(help="Modelo Odoo, ej: 'purchase.order'")],
    ids: Annotated[str, typer.Argument(help="IDs separados por coma o JSON list.")],
    values: Annotated[
        str,
        typer.Option(
            "--values",
            "-v",
            help='Valores como JSON, ej: \'{"date_planned":"2026-05-24"}\'.',
        ),
    ],
    reason: Annotated[
        str | None,
        typer.Option("--reason", "-r", help="Razón del cambio (obligatoria en masivos)."),
    ] = None,
    output: Annotated[str, typer.Option("--output", "-o")] = "json",
) -> None:
    """Update de registros (con flujo de aprobación)."""
    rt = setup()
    massive_threshold = rt.rbac.massive_threshold
    expiry = rt.rbac.pending_expiry_minutes

    try:
        perm = rt.rbac.check_model_access(rt.cfg.role, model, "write")
    except PermissionDenied as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=1) from e

    try:
        if ids.strip().startswith("["):
            id_list = json.loads(ids)
        else:
            id_list = [int(x.strip()) for x in ids.split(",") if x.strip()]
        values_dict = json.loads(values)
    except (json.JSONDecodeError, ValueError) as e:
        typer.echo(f"error: input inválido: {e}", err=True)
        raise typer.Exit(code=1) from e

    values_dict = rt.rbac.strip_protected_fields(values_dict)
    for f in perm.fields_denied:
        values_dict.pop(f, None)
    if not values_dict:
        typer.echo("error: no quedan campos escribibles tras filtrar permisos", err=True)
        raise typer.Exit(code=1)

    changed_fields = list(values_dict.keys())
    read_fields = list(set(changed_fields + ["name", "display_name"]))

    try:
        old_records = rt.client.execute_kw(model, "read", [id_list], {"fields": read_fields})
    except OdooError as e:
        typer.echo(f"error leyendo old_values: {e}", err=True)
        raise typer.Exit(code=2) from e

    is_massive = len(id_list) > massive_threshold
    preview = build_write_preview(model, old_records, values_dict)
    requires_approval = needs_approval(rt.rbac, rt.cfg.role, is_massive=is_massive)
    status = "approval_required" if requires_approval else "pending"

    pending_id = rt.audit.create_pending(
        action="write",
        model=model,
        record_ids=id_list,
        old_values=old_records,
        new_values=values_dict,
        preview=preview,
        is_massive=is_massive,
        record_count=len(id_list),
        details=build_details(rt.cfg, fields=changed_fields, reason=reason),
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
            role=rt.cfg.role,
            action="write",
            model=model,
            record_count=len(id_list),
            preview=preview,
            reason=reason,
            audit=rt.audit,
        )
        response["status"] = "approval_required"
        response["notified_channel"] = channel
        response["notified_message_id"] = msg_id
        response["instructions"] = (
            f"Solicitud enviada a {channel} para aprobación humana. "
            "Esta acción NO se puede confirmar desde aquí; debe aprobarse externamente."
        )
        emit(response, fmt=output)
        raise typer.Exit(code=3)

    response["status"] = "pending"
    response["instructions"] = (
        f"Si el preview es correcto, ejecutá: puya odoo confirm {pending_id}\n"
        f"Si querés rechazar, ejecutá: puya odoo cancel {pending_id}"
    )
    emit(response, fmt=output)
