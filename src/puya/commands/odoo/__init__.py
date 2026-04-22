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

from puya.commands.odoo.call import call_command
from puya.commands.odoo.cancel import cancel_command
from puya.commands.odoo.confirm import confirm_command
from puya.commands.odoo.count import count_command
from puya.commands.odoo.create import create_command
from puya.commands.odoo.delete import delete_command
from puya.commands.odoo.fields import fields_command
from puya.commands.odoo.pending import pending_command
from puya.commands.odoo.read import read_command
from puya.commands.odoo.search import search_command
from puya.commands.odoo.status import status_command
from puya.commands.odoo.write import write_command

app = typer.Typer(
    name="odoo",
    help="Operaciones contra Odoo via XML-RPC.",
    no_args_is_help=True,
)

# Read-only
app.command(name="status")(status_command)
app.command(name="search")(search_command)
app.command(name="count")(count_command)
app.command(name="fields")(fields_command)
app.command(name="read")(read_command)

# Mutations (preview + approval flow)
app.command(name="write")(write_command)
app.command(name="create")(create_command)
app.command(name="delete")(delete_command)
app.command(name="call")(call_command)

# Pending lifecycle
app.command(name="confirm")(confirm_command)
app.command(name="cancel")(cancel_command)
app.command(name="pending")(pending_command)
