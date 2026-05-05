"""Subcomandos `puya odoo *` — todos van vía HTTP a /api/cli-odoo/* en puya-chat.

Capa fina sobre `puya.lib.client.PuyaClient`. Sin RBAC ni Odoo client del
lado del CLI — la lógica vive server-side en puya-chat. Esto deja al CLI
en ~200 líneas.
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
    help="Operaciones contra Odoo via puya-chat proxy.",
    no_args_is_help=True,
)

# Read
app.command(name="status")(status_command)
app.command(name="search")(search_command)
app.command(name="count")(count_command)
app.command(name="fields")(fields_command)
app.command(name="read")(read_command)

# Mutations (siempre approval humano via Slack)
app.command(name="write")(write_command)
app.command(name="create")(create_command)
app.command(name="delete")(delete_command)
app.command(name="call")(call_command)

# Pending lifecycle (consumer self-service: list + cancel; confirm es server-side)
app.command(name="confirm")(confirm_command)
app.command(name="cancel")(cancel_command)
app.command(name="pending")(pending_command)
