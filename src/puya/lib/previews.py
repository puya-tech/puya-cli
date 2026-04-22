"""Builders de preview legibles para writes/creates/deletes/executes.

Porteado desde puya-odoo-mcp. Sirven para que humanos (en Slack/Odoo UI)
vean qué cambios se aplicarían antes de aprobar.
"""

from __future__ import annotations


def format_val(val: object) -> str:
    if val is False or val is None:
        return "(vacío)"
    if isinstance(val, list) and len(val) == 2 and isinstance(val[0], int):
        # Odoo many2one: [id, "display_name"]
        return str(val[1])
    if isinstance(val, list):
        if len(val) > 5:
            return f"[{len(val)} items]"
        return str(val)
    if isinstance(val, str) and len(val) > 100:
        return val[:100] + "..."
    return str(val)


def build_write_preview(model: str, old_records: list[dict], new_values: dict) -> str:
    plural = "s" if len(old_records) != 1 else ""
    lines = [f"Cambios en {model} ({len(old_records)} registro{plural}):\n"]

    for rec in old_records:
        rec_id = rec.get("id", "?")
        name = rec.get("name") or rec.get("display_name") or rec.get("x_name") or f"#{rec_id}"
        lines.append(f"  Registro #{rec_id} ({name}):")
        for field, new_val in new_values.items():
            old_val = rec.get(field, "—")
            if old_val != new_val:
                lines.append(f"    {field}: {format_val(old_val)} -> {format_val(new_val)}")
            else:
                lines.append(f"    {field}: {format_val(old_val)} (sin cambio)")
        lines.append("")

    return "\n".join(lines)


def build_create_preview(model: str, values: dict) -> str:
    lines = [f"Crear nuevo registro en {model}:\n"]
    for field, val in values.items():
        lines.append(f"  {field}: {format_val(val)}")
    return "\n".join(lines)


def build_delete_preview(model: str, records: list[dict]) -> str:
    plural = "s" if len(records) != 1 else ""
    lines = [f"Eliminar {len(records)} registro{plural} de {model}:\n"]
    for rec in records:
        rec_id = rec.get("id", "?")
        name = rec.get("name") or rec.get("display_name") or f"#{rec_id}"
        lines.append(f"  #{rec_id} — {name}")
    return "\n".join(lines)


def build_execute_preview(model: str, method: str, record_ids: list) -> str:
    if record_ids:
        plural = "s" if len(record_ids) != 1 else ""
        return f"Ejecutar {model}.{method}() en {len(record_ids)} registro{plural}: {record_ids}"
    return f"Ejecutar {model}.{method}()"
