"""Entry point del CLI: registra los subcomandos por dominio.

Cada dominio (`odoo`, `notion`, `supabase`, ...) vive en `puya.commands.<dominio>`
y expone un `app` Typer que se monta acá. Mantener este archivo CHICO — el
roteo es lo único que va acá; toda la lógica vive en sus módulos.
"""

from __future__ import annotations

import typer

from puya import __version__
from puya.commands.odoo import app as odoo_app

app = typer.Typer(
    name="puya",
    help="Puya Tech CLI: cliente unificado para Odoo, Notion, Supabase y más.",
    no_args_is_help=True,
    add_completion=True,
    rich_markup_mode="rich",
)

# ── Subcomandos por dominio ─────────────────────────────────
app.add_typer(odoo_app, name="odoo", help="Operaciones contra Odoo (search, write, create, ...)")


@app.command()
def version() -> None:
    """Muestra la versión instalada."""
    typer.echo(f"puya {__version__}")


if __name__ == "__main__":
    app()
