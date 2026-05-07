"""Subcomandos `puya tool *` — invocador genérico de endpoints custom.

El catálogo de tools vive server-side en `puya_cli.custom_endpoints` y la
relación con cada api_key en `puya_cli.api_key_custom_endpoints`. Esto
significa que cuando el operador suma una tool nueva (registra el slug
+ habilita en una key), el cliente la descubre dinámicamente — no hace
falta release del CLI.

Comandos:
  puya tool list                              # tools habilitadas para mi key
  puya tool call <slug> --json '<payload>'    # POST /api/custom/<slug>
"""

from __future__ import annotations

import typer

from puya.commands.tool.call import call_command
from puya.commands.tool.list_cmd import list_command

app = typer.Typer(
    name="tool",
    help="Tools custom registradas server-side. Catálogo dinámico por api_key.",
    no_args_is_help=True,
)

app.command(name="list")(list_command)
app.command(name="call")(call_command)
