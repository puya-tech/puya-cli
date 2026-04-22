"""Subcomandos de Odoo: search, write, create, etc.

Capa 1 del diseño (low-level passthrough). Cada comando es un wrapper fino
sobre `puya.lib.odoo_client.OdooClient`, con validación de RBAC vía
`puya.lib.rbac.RBACEngine` y registro en audit log via `puya.lib.audit`.

Los comandos high-level (stock_adjust, purchase_modify_date, etc.) viven
en otros módulos (puya.commands.stock, puya.commands.purchase) y se
construyen en una iteración posterior, junto con sus skills.
"""

from __future__ import annotations

import typer

from puya.commands.odoo.search import search_command
from puya.commands.odoo.status import status_command

app = typer.Typer(
    name="odoo",
    help="Operaciones contra Odoo via XML-RPC.",
    no_args_is_help=True,
)

app.command(name="status")(status_command)
app.command(name="search")(search_command)
