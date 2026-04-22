"""Helper de salida unificado: json | table | raw.

JSON es el default para agentes (parseable). Table para humanos (Rich).
Raw vuelca el objeto Python sin formatear (debug).
"""

from __future__ import annotations

import json
import sys
from typing import Any

import typer
from rich.console import Console
from rich.table import Table


def emit(data: Any, fmt: str = "json") -> None:
    """Imprime `data` en el formato indicado a stdout."""
    fmt = fmt.lower()
    if fmt == "json":
        json.dump(data, sys.stdout, ensure_ascii=False, default=str, indent=2)
        sys.stdout.write("\n")
    elif fmt == "table":
        _emit_table(data)
    elif fmt == "raw":
        sys.stdout.write(repr(data) + "\n")
    else:
        typer.echo(f"error: --output desconocido: {fmt}", err=True)
        raise typer.Exit(code=1)


def _emit_table(data: Any) -> None:
    console = Console()
    if isinstance(data, dict):
        table = Table(show_header=True, header_style="bold")
        table.add_column("Key", style="cyan")
        table.add_column("Value")
        for k, v in data.items():
            table.add_row(str(k), _format_cell(v))
        console.print(table)
    elif isinstance(data, list):
        if not data:
            console.print("[dim](sin resultados)[/dim]")
            return
        if isinstance(data[0], dict):
            keys = list(data[0].keys())
            table = Table(show_header=True, header_style="bold")
            for k in keys:
                table.add_column(k, style="cyan" if k == "id" else None)
            for row in data:
                table.add_row(*[_format_cell(row.get(k)) for k in keys])
            console.print(table)
        else:
            for item in data:
                console.print(item)
    else:
        console.print(data)


def _format_cell(v: Any) -> str:
    if v is None or v is False:
        return ""
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False, default=str)
    return str(v)
