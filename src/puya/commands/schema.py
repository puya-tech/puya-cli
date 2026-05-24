"""`puya schema` — emite el catálogo completo de comandos como JSON.

Pensado para agentes (Claude Code, Codex, etc.) que ven el CLI por
primera vez en una máquina y necesitan descubrir qué comandos existen,
qué argumentos toman, qué tipo y qué default, sin scrapear `--help`
(que va con cajitas Rich y no es estable).

Sin red. Sin auth. Idempotente. Output JSON estable.

Forma del output:

    {
      "schema_version": "1",
      "cli_version": "1.4.0",
      "command": {
        "name": "puya",
        "help": "...",
        "subcommands": {
          "odoo": {
            "name": "odoo",
            "help": "...",
            "subcommands": {
              "search": {
                "name": "search",
                "path": "odoo search",
                "help": "...",
                "params": [
                  {"name": "model", "kind": "argument", "type": "TEXT",
                   "required": true, "help": "..."},
                  {"name": "domain", "kind": "option", "type": "TEXT",
                   "flags": ["--domain", "-d"], "default": "[]",
                   "required": false, "help": "..."},
                  ...
                ]
              }, ...
            }
          }, ...
        }
      }
    }

Decisión: dejamos el endpoint HTTP (`/api/cli-odoo/*`) FUERA del schema
en v1 porque se infiere del path del comando y agregarlo invitaría a
drift. Si en el futuro hace falta para alguna tool custom, se suma como
clave opcional `endpoint`.
"""

from __future__ import annotations

import click
import typer

from puya.lib.output import emit

SCHEMA_VERSION = "1"


def _serialize_param(param: click.Parameter) -> dict:
    type_name = getattr(param.type, "name", str(param.type))
    default = param.default
    if callable(default):
        default = None

    out: dict[str, object] = {
        "name": param.name,
        "kind": "argument" if isinstance(param, click.Argument) else "option",
        "type": type_name,
        "required": bool(param.required),
        "help": getattr(param, "help", None),
    }
    if isinstance(param, click.Option):
        out["flags"] = list(param.opts)
        out["default"] = default
    return out


def _serialize_command(cmd: click.Command, path: list[str]) -> dict:
    return {
        "name": cmd.name,
        "path": " ".join(path),
        "help": (cmd.help or cmd.short_help or "").strip() or None,
        "params": [_serialize_param(p) for p in cmd.params if p.name != "help"],
    }


def _serialize_group(group: click.Group, path: list[str]) -> dict:
    subcommands: dict[str, dict] = {}
    for name in sorted(group.commands.keys()):
        cmd = group.commands[name]
        sub_path = path + [name]
        if isinstance(cmd, click.Group):
            subcommands[name] = _serialize_group(cmd, sub_path)
        else:
            subcommands[name] = _serialize_command(cmd, sub_path)
    return {
        "name": group.name,
        "path": " ".join(path),
        "help": (group.help or "").strip() or None,
        "subcommands": subcommands,
    }


def schema_command() -> None:
    """Emite el catálogo de comandos como JSON estable (no toca red)."""
    # Import diferido para evitar ciclo con `puya.cli`.
    from puya import __version__
    from puya.cli import app

    cli_group = typer.main.get_command(app)
    assert isinstance(cli_group, click.Group), "root app debe ser un Group"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "cli_version": __version__,
        "command": _serialize_group(cli_group, ["puya"]),
    }
    emit(payload, fmt="json")
