"""`puya odoo pending` — lista pending actions del usuario actual."""

from __future__ import annotations

from typing import Annotated

import typer

from puya.lib.output import emit
from puya.lib.runtime import setup


def pending_command(
    limit: Annotated[int, typer.Option("--limit", "-l")] = 20,
    output: Annotated[str, typer.Option("--output", "-o")] = "json",
) -> None:
    """Lista pending actions del usuario actual (status='pending')."""
    rt = setup()
    rows = rt.audit.query_pending(user=rt.username, limit=limit)
    emit(rows or [], fmt=output)
