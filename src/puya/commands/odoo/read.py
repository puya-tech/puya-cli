"""`puya odoo read <model> <ids>` — lee registros por id."""

from __future__ import annotations

import json
from typing import Annotated

import typer

from puya.lib.odoo_client import OdooError
from puya.lib.output import emit
from puya.lib.rbac import PermissionDenied
from puya.lib.runtime import setup


def read_command(
    model: Annotated[str, typer.Argument(help="Modelo Odoo, ej: 'res.partner'")],
    ids: Annotated[
        str,
        typer.Argument(
            help="IDs separados por coma o JSON list, ej: '1,2,3' o '[1,2,3]'.",
        ),
    ],
    fields: Annotated[
        str | None,
        typer.Option("--fields", "-f", help="Campos separados por coma. Default: todos."),
    ] = None,
    output: Annotated[str, typer.Option("--output", "-o")] = "json",
) -> None:
    """Lee registros específicos por id (read)."""
    rt = setup()

    try:
        perm = rt.rbac.check_model_access(rt.cfg.role, model, "search_read")
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

    # Ownership check si hay domain_filter en el role
    if perm.domain_filter:
        scoped = rt.rbac.inject_domain(perm, [("id", "in", id_list)], rt.client.uid)
        try:
            owned = rt.client.execute_kw(model, "search", [scoped])
        except OdooError as e:
            typer.echo(f"error: {e}", err=True)
            raise typer.Exit(code=2) from e
        denied = set(id_list) - set(owned)
        if denied:
            typer.echo(
                f"error: registros {sorted(denied)} fuera de tu scope",
                err=True,
            )
            raise typer.Exit(code=1)
        id_list = owned

    field_list = [f.strip() for f in fields.split(",")] if fields else []
    if field_list:
        field_list = rt.rbac.filter_fields(perm, field_list)

    try:
        result = rt.client.execute_kw(model, "read", [id_list], {"fields": field_list})
    except OdooError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=2) from e

    if perm.fields_denied and not field_list:
        for record in result:
            for f in perm.fields_denied:
                record.pop(f, None)

    emit(result, fmt=output)
