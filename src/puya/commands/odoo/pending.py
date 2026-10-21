"""`puya odoo pending [id]` — lista o detalle de pending actions del consumer.

Sin ID: lista los pendings del consumer logueado, más nuevos primero, en
vista compacta (default 10). Cada uno trae su desenlace (`outcome`).
Con ID: detalle del pending, incluyendo resultados si la acción fue
'search' y ya está ejecutada.

Para esperar a que uno se resuelva: `puya odoo wait <id>`.
"""

from __future__ import annotations

from typing import Annotated
from urllib.parse import urlencode

import typer

from puya.commands._helpers import EnvOption, handle_api_error, setup_client
from puya.lib.client import PuyaApiError
from puya.lib.output import emit

VALID_STATUSES = ("pending", "executed", "failed", "rejected", "cancelled", "expired")
# Nombres viejos del filtro (antes era el status crudo de la base).
LEGACY_STATUSES = {"confirmed": "executed"}


def _summarize_for_table(pendings: list) -> list[dict]:
    """Extrae columnas clave para vista tabla legible."""
    rows = []
    for p in pendings:
        error = p.get("error") or {}
        rows.append(
            {
                "id": p.get("id"),
                "outcome": p.get("outcome") or p.get("status"),
                "action": p.get("action"),
                "model": p.get("model"),
                "ids": p.get("record_ids") or [],
                "reason": (p.get("reason") or "")[:40],
                "error": (error.get("message") or "")[:40],
                "env": p.get("target_env") or "",
                "created": (p.get("created_at") or "")[:16],
            }
        )
    return rows


def pending_command(
    pending_id: Annotated[
        int | None,
        typer.Argument(help="ID del pending. Si se omite, lista los últimos."),
    ] = None,
    status: Annotated[
        str | None,
        typer.Option(
            "--status",
            "-s",
            help="Filtrar por desenlace: " + ", ".join(VALID_STATUSES) + ".",
        ),
    ] = None,
    limit: Annotated[
        int | None,
        typer.Option("--limit", "-l", help="Máximo de filas (default 10, máx 50)."),
    ] = None,
    output: Annotated[str, typer.Option("--output", "-o")] = "json",
    env: EnvOption = None,
) -> None:
    """Lista pendings o muestra el detalle de uno (con resultados si aplica)."""
    params: dict[str, str] = {}
    if status:
        s = status.strip().lower()
        s = LEGACY_STATUSES.get(s, s)
        if s not in VALID_STATUSES:
            typer.echo(
                f"error: status inválido '{s}'. Permitidos: {', '.join(VALID_STATUSES)}",
                err=True,
            )
            raise typer.Exit(code=1)
        params["status"] = s
    if limit is not None:
        params["limit"] = str(limit)

    _, client = setup_client(env=env)
    with client:
        try:
            if pending_id is None:
                query = f"?{urlencode(params)}" if params else ""
                _, body = client.get(f"/api/cli-odoo/pending{query}")
                pendings = body.get("pendings", []) if isinstance(body, dict) else body
                if output == "table":
                    emit(_summarize_for_table(pendings), fmt="table")
                else:
                    emit(pendings, fmt=output)
            else:
                _, body = client.get(f"/api/cli-odoo/pending/{pending_id}")
                emit(body, fmt=output)
        except PuyaApiError as e:
            handle_api_error(e)
            return
