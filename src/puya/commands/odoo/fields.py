"""`puya odoo fields <model>` — fields_get contra Odoo (descubrir schema)."""

from __future__ import annotations

from typing import Annotated

import typer

from puya.lib.odoo_client import OdooError
from puya.lib.output import emit
from puya.lib.rbac import PermissionDenied
from puya.lib.runtime import setup


def fields_command(
    model: Annotated[str, typer.Argument(help="Modelo Odoo, ej: 'product.product'")],
    attributes: Annotated[
        str | None,
        typer.Option(
            "--attributes",
            "-a",
            help="Atributos separados por coma. Default: string,type,required,readonly.",
        ),
    ] = None,
    output: Annotated[str, typer.Option("--output", "-o")] = "json",
) -> None:
    """Devuelve definición de campos de un modelo (útil para discovery)."""
    rt = setup()

    try:
        rt.rbac.check_model_access(rt.role, model, "search_read")
    except PermissionDenied as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=1) from e

    attrs = (
        [a.strip() for a in attributes.split(",")]
        if attributes
        else ["string", "type", "required", "readonly"]
    )

    try:
        result = rt.client.execute_kw(model, "fields_get", [], {"attributes": attrs})
    except OdooError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=2) from e

    emit(result, fmt=output)
