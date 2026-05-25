"""`puya odoo pending [id]` — lista o detalle de pending actions del consumer.

Sin ID: lista todos los pendings del consumer logueado.
Con ID: detalle del pending, incluyendo resultados si la acción fue
'search' y ya está confirmed.
"""

from __future__ import annotations

from typing import Annotated

import typer

from puya.commands._helpers import EnvOption, handle_api_error, setup_client
from puya.lib.client import PuyaApiError
from puya.lib.output import emit

VALID_STATUSES = ("pending", "confirmed", "cancelled", "expired", "rejected")


def pending_command(
    pending_id: Annotated[
        int | None,
        typer.Argument(help="ID del pending. Si se omite, lista todos."),
    ] = None,
    status: Annotated[
        str | None,
        typer.Option(
            "--status",
            "-s",
            help="Filtrar por status: pending, confirmed, cancelled, expired, rejected.",
        ),
    ] = None,
    output: Annotated[str, typer.Option("--output", "-o")] = "json",
    env: EnvOption = None,
) -> None:
    """Lista pendings o muestra el detalle de uno (con resultados si aplica)."""
    _, client = setup_client(env=env)
    with client:
        try:
            if pending_id is None:
                _, body = client.get("/api/cli-odoo/pending")
                pendings = body.get("pendings", []) if isinstance(body, dict) else body
                if status:
                    s = status.strip().lower()
                    if s not in VALID_STATUSES:
                        from puya.lib.output import emit_hint

                        emit_hint(
                            "status_filter",
                            f"status inválido '{s}'. Permitidos: {', '.join(VALID_STATUSES)}",
                        )
                    else:
                        pendings = [p for p in pendings if p.get("status") == s]
                emit(pendings, fmt=output)
            else:
                _, body = client.get(f"/api/cli-odoo/pending/{pending_id}")
                emit(body, fmt=output)
        except PuyaApiError as e:
            handle_api_error(e)
            return
