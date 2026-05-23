"""Entry point del CLI: registra los subcomandos por dominio.

Cada dominio (`odoo`, `notion`, `supabase`, ...) vive en `puya.commands.<dominio>`
y expone un `app` Typer que se monta acá. Mantener este archivo CHICO — el
roteo es lo único que va acá; toda la lógica vive en sus módulos.
"""

from __future__ import annotations

import typer

from puya import __version__
from puya.commands.account import account_command
from puya.commands.odoo import app as odoo_app
from puya.commands.tool import app as tool_app

app = typer.Typer(
    name="puya",
    help="Puya Tech CLI: thin HTTP client al CLI proxy de puya-chat.",
    no_args_is_help=True,
    add_completion=True,
    rich_markup_mode="rich",
)

# ── Subcomandos por dominio ─────────────────────────────────
app.add_typer(odoo_app, name="odoo", help="Operaciones contra Odoo via puya-chat proxy.")
app.add_typer(tool_app, name="tool", help="Tools custom registradas server-side.")

# ── Comandos top-level ──────────────────────────────────────
app.command(name="account", help="Info de mi consumer + listado de slots.")(account_command)


@app.command()
def version() -> None:
    """Muestra la versión instalada."""
    typer.echo(f"puya {__version__}")


if __name__ == "__main__":
    app()
