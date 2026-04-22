"""`puya odoo create <model> --values <json>` — preview de create."""

from __future__ import annotations

import json
from typing import Annotated

import typer

from puya.lib.approvals import build_details
from puya.lib.output import emit
from puya.lib.previews import build_create_preview
from puya.lib.rbac import PermissionDenied
from puya.lib.runtime import setup


def create_command(
    model: Annotated[str, typer.Argument(help="Modelo Odoo, ej: 'res.partner'")],
    values: Annotated[
        str, typer.Option("--values", "-v", help="Valores del nuevo record como JSON.")
    ],
    output: Annotated[str, typer.Option("--output", "-o")] = "json",
) -> None:
    """Crea un registro nuevo (con flujo de preview/confirm)."""
    rt = setup()
    expiry = rt.rbac.pending_expiry_minutes

    try:
        perm = rt.rbac.check_model_access(rt.role, model, "create")
    except PermissionDenied as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=1) from e

    try:
        values_dict = json.loads(values)
    except json.JSONDecodeError as e:
        typer.echo(f"error: --values no es JSON válido: {e}", err=True)
        raise typer.Exit(code=1) from e

    values_dict = rt.rbac.strip_protected_fields(values_dict)
    for f in perm.fields_denied:
        values_dict.pop(f, None)

    preview = build_create_preview(model, values_dict)

    pending_id = rt.audit.create_pending(
        action="create",
        model=model,
        record_ids=[],
        old_values=None,
        new_values=values_dict,
        preview=preview,
        is_massive=False,
        record_count=1,
        details=build_details(rt.cfg),
        expiry_minutes=expiry,
    )

    emit(
        {
            "pending_id": pending_id,
            "status": "pending",
            "model": model,
            "preview": preview,
            "instructions": (
                f"Si el preview es correcto: puya odoo confirm {pending_id}\n"
                f"Si querés rechazar: puya odoo cancel {pending_id}"
            ),
        },
        fmt=output,
    )
