"""Subcomandos `puya image *` — flujo de imágenes de producto (IA) vía puya-chat.

Capa fina sobre `puya.lib.client.PuyaClient`. La lógica (Gemini, storage,
Slack, resolución de la solicitud pendiente en Odoo) vive server-side en
puya-chat (`/api/image/*`).
"""

from __future__ import annotations

import typer

from puya.commands.image.refine import refine_command

app = typer.Typer(
    name="image",
    help="Imágenes de producto generadas por IA (refinar candidatas pendientes).",
    no_args_is_help=True,
)

app.command(name="refine")(refine_command)
