"""Sub-app `puya skills *` — manejo de skills procedimentales.

Las skills viven en el repo puya-tech/puya-context y se sirven via
puya-chat (`/api/cli-account/skills`). Este sub-app permite:

  puya skills list                       Listar todas (con estado vs local)
  puya skills show <slug>                Markdown raw a stdout
  puya skills install <slug> [--to PATH] Descargar + instalar
  puya skills check                      Comparar local vs remoto
  puya skills update [<slug>] [--all]    Refrescar outdated
  puya skills diff <slug>                Diff local vs remoto
  puya skills uninstall <slug>           Borrar local + remover de state

State manifest en ~/.puya/skills-state.json — trackea hash + path de
cada skill instalada.

Estados (visible en `check`):
  ✅ up-to-date   hash local == remoto
  ⚠️  outdated    hash local != remoto
  🆕 available    server la lista, no instalada
  🗑️  orphan      local existe pero server no la mantiene (o no tracked)
"""

from __future__ import annotations

import difflib
import json as json_lib
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from puya.commands._helpers import EnvOption
from puya.commands.skills._api import (
    RemoteSkill,
    fetch_remote_skills,
    fetch_skill_raw,
)
from puya.commands.skills.state import (
    InstalledSkill,
    compute_hash,
    default_install_dir,
    load_state,
    record_install,
    remove_record,
)
from puya.lib.client import PuyaApiError, PuyaClient
from puya.lib.config import load_config, validate_config

app = typer.Typer(
    name="skills",
    help="Manejo de skills procedimentales (list / show / install / check / update / diff / uninstall).",
    no_args_is_help=True,
)


def _client(env: str | None) -> PuyaClient:
    cfg = load_config(env_override=env)
    err = validate_config(cfg, env_override=env)
    if err:
        typer.echo(f"error: {err}", err=True)
        raise typer.Exit(code=1)
    return PuyaClient(cfg)


def _emoji_state(state: str) -> str:
    return {
        "up-to-date": "✅",
        "outdated": "⚠️",
        "available": "🆕",
        "orphan": "🗑️",
    }.get(state, "❓")


def _color_state(state: str) -> str:
    return {
        "up-to-date": "green",
        "outdated": "yellow",
        "available": "cyan",
        "orphan": "red",
    }.get(state, "white")


def _local_hash_from_disk(local: InstalledSkill) -> str | None:
    """Re-hashea el archivo en disk. Si fue movido/borrado, devuelve None."""
    try:
        text = Path(local.path).read_text(encoding="utf-8")
    except OSError:
        return None
    return compute_hash(text)


def _compute_states(
    remote: list[RemoteSkill],
    installed: dict[str, InstalledSkill],
) -> dict[str, str]:
    """Mapea slug → estado. Cubre todos los slugs (remotos + locales).

    Re-hashea cada archivo local en disk (no confía solo en state.json)
    para detectar modificaciones manuales del archivo. Costo: ~1 file
    read por skill instalada, despreciable.
    """
    states: dict[str, str] = {}
    remote_slugs = {r.slug for r in remote}
    remote_by_slug = {r.slug: r for r in remote}

    for r in remote:
        local = installed.get(r.slug)
        if not local:
            states[r.slug] = "available"
            continue
        disk_hash = _local_hash_from_disk(local)
        if disk_hash is None:
            # Archivo borrado/movido manualmente — state inconsistente.
            states[r.slug] = "orphan"
        elif disk_hash == r.content_hash:
            states[r.slug] = "up-to-date"
        else:
            states[r.slug] = "outdated"

    for slug in installed:
        if slug not in remote_slugs:
            states[slug] = "orphan"
        elif slug not in states:
            # safety
            local = installed[slug]
            r = remote_by_slug.get(slug)
            disk_hash = _local_hash_from_disk(local)
            if r and disk_hash == r.content_hash:
                states[slug] = "up-to-date"
            else:
                states[slug] = "outdated"

    return states


# ───────────────────────────────────────────────────────────
# list
# ───────────────────────────────────────────────────────────


@app.command("list")
def list_command(
    output: Annotated[str, typer.Option("--output", "-o")] = "table",
    check: Annotated[
        bool, typer.Option("--check", help="Cruzar con state local y mostrar columna estado.")
    ] = False,
    env: EnvOption = None,
) -> None:
    """Listar skills disponibles en el servidor."""
    with _client(env) as client:
        try:
            remote = fetch_remote_skills(client)
        except PuyaApiError as e:
            typer.echo(f"error: {e}", err=True)
            raise typer.Exit(code=e.exit_code) from e

    if output.lower() == "json":
        installed = load_state() if check else {}
        states = _compute_states(remote, installed) if check else {}
        data = []
        for r in remote:
            entry = {
                "slug": r.slug,
                "name": r.name,
                "description": r.description,
                "content_hash": r.content_hash,
            }
            if check:
                entry["state"] = states.get(r.slug, "available")
                if r.slug in installed:
                    entry["local_path"] = installed[r.slug].path
            data.append(entry)
        if check:
            for slug, st in states.items():
                if st == "orphan":
                    data.append(
                        {
                            "slug": slug,
                            "state": "orphan",
                            "local_path": installed[slug].path,
                        }
                    )
        sys.stdout.write(json_lib.dumps(data, indent=2, ensure_ascii=False) + "\n")
        return

    console = Console()
    if not remote:
        console.print("[dim]No hay skills disponibles en el servidor.[/dim]")
        return

    table = Table(show_lines=False)
    table.add_column("slug", style="bold")
    table.add_column("description")
    table.add_column("hash", style="dim")
    if check:
        table.add_column("state")

    installed = load_state() if check else {}
    states = _compute_states(remote, installed) if check else {}

    for r in remote:
        row = [r.slug, r.description, r.content_hash]
        if check:
            st = states.get(r.slug, "available")
            row.append(f"[{_color_state(st)}]{_emoji_state(st)} {st}[/{_color_state(st)}]")
        table.add_row(*row)

    if check:
        # Mostrar orphans al final
        for slug, st in states.items():
            if st == "orphan":
                table.add_row(
                    slug,
                    "[dim]instalada localmente, no en server[/dim]",
                    "—",
                    f"[{_color_state(st)}]{_emoji_state(st)} {st}[/{_color_state(st)}]",
                )

    console.print(table)


# ───────────────────────────────────────────────────────────
# show
# ───────────────────────────────────────────────────────────


@app.command("show")
def show_command(
    slug: Annotated[str, typer.Argument(help="Slug de la skill (ej. puya-modulo-investigar)")],
    env: EnvOption = None,
) -> None:
    """Imprime el SKILL.md raw de la skill a stdout."""
    with _client(env) as client:
        try:
            content = fetch_skill_raw(client, slug)
        except PuyaApiError as e:
            typer.echo(f"error: {e}", err=True)
            raise typer.Exit(code=e.exit_code) from e
    sys.stdout.write(content)
    if not content.endswith("\n"):
        sys.stdout.write("\n")


# ───────────────────────────────────────────────────────────
# install
# ───────────────────────────────────────────────────────────


def _install_one(client: PuyaClient, slug: str, dest_dir: Path) -> InstalledSkill:
    content = fetch_skill_raw(client, slug)
    skill_dir = dest_dir / slug
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_path = skill_dir / "SKILL.md"
    skill_path.write_text(content, encoding="utf-8")
    return record_install(slug, skill_path, content)


@app.command("install")
def install_command(
    slug: Annotated[str, typer.Argument(help="Slug de la skill a instalar")],
    to: Annotated[
        Path | None,
        typer.Option(
            "--to",
            help="Directorio destino (default: auto-detect entre "
            "~/.claude/skills, ~/.codex/skills, ~/.config/opencode/skills).",
        ),
    ] = None,
    env: EnvOption = None,
) -> None:
    """Descarga e instala una skill en el directorio destino."""
    dest = to or default_install_dir()
    with _client(env) as client:
        try:
            installed = _install_one(client, slug, dest)
        except PuyaApiError as e:
            typer.echo(f"error: {e}", err=True)
            raise typer.Exit(code=e.exit_code) from e
    typer.echo(f"✅ installed {slug} → {installed.path}\n   hash={installed.content_hash}")


# ───────────────────────────────────────────────────────────
# check
# ───────────────────────────────────────────────────────────


@app.command("check")
def check_command(
    output: Annotated[str, typer.Option("--output", "-o")] = "table",
    env: EnvOption = None,
) -> None:
    """Compara skills locales (state.json) vs server. Exit 0 si todo OK,
    exit 1 si hay outdated/orphan (útil para CI).
    """
    with _client(env) as client:
        try:
            remote = fetch_remote_skills(client)
        except PuyaApiError as e:
            typer.echo(f"error: {e}", err=True)
            raise typer.Exit(code=e.exit_code) from e

    installed = load_state()
    states = _compute_states(remote, installed)

    drift = {s: st for s, st in states.items() if st in ("outdated", "orphan")}
    available_count = sum(1 for st in states.values() if st == "available")

    if output.lower() == "json":
        sys.stdout.write(
            json_lib.dumps(
                {
                    "states": states,
                    "drift_count": len(drift),
                    "available_count": available_count,
                },
                indent=2,
            )
            + "\n"
        )
        if drift:
            raise typer.Exit(code=1)
        return

    console = Console()
    if not states:
        console.print("[dim]No hay skills instaladas ni disponibles.[/dim]")
        return

    table = Table(show_lines=False)
    table.add_column("slug", style="bold")
    table.add_column("state")
    table.add_column("detalle", style="dim")

    remote_by_slug = {r.slug: r for r in remote}
    for slug, st in sorted(states.items()):
        if st == "orphan":
            detail = f"local: {installed[slug].path}"
        elif st == "outdated":
            r = remote_by_slug.get(slug)
            detail = f"local={installed[slug].content_hash}  server={r.content_hash if r else '?'}"
        elif st == "available":
            detail = f"server={remote_by_slug[slug].content_hash}"
        else:
            detail = ""
        table.add_row(
            slug,
            f"[{_color_state(st)}]{_emoji_state(st)} {st}[/{_color_state(st)}]",
            detail,
        )

    console.print(table)
    if drift:
        console.print(
            f"\n[yellow]{len(drift)} skill(s) con drift.[/yellow] "
            f"Corré [bold]puya skills update[/bold] (outdated) o "
            f"[bold]puya skills uninstall <slug>[/bold] (orphan)."
        )
        raise typer.Exit(code=1)
    if available_count > 0:
        console.print(
            f"\n[dim]{available_count} skill(s) disponibles para instalar — "
            f"`puya skills list --check` para verlas.[/dim]"
        )


# ───────────────────────────────────────────────────────────
# update
# ───────────────────────────────────────────────────────────


@app.command("update")
def update_command(
    slug: Annotated[
        str | None, typer.Argument(help="Slug específico (default: todas outdated).")
    ] = None,
    all_flag: Annotated[
        bool,
        typer.Option("--all", help="Además de outdated, instala available y borra orphan."),
    ] = False,
    env: EnvOption = None,
) -> None:
    """Actualizar skill(s) outdated desde el servidor. Sin args = todas las outdated."""
    with _client(env) as client:
        try:
            remote = fetch_remote_skills(client)
        except PuyaApiError as e:
            typer.echo(f"error: {e}", err=True)
            raise typer.Exit(code=e.exit_code) from e

        installed = load_state()
        states = _compute_states(remote, installed)

        targets: list[tuple[str, str]] = []  # (slug, state)
        if slug:
            if slug not in states:
                typer.echo(f"error: '{slug}' no existe ni local ni en server", err=True)
                raise typer.Exit(code=1)
            targets.append((slug, states[slug]))
        else:
            for s, st in states.items():
                if st == "outdated" or all_flag and st in ("available", "orphan"):
                    targets.append((s, st))

        if not targets:
            typer.echo("nothing to update.")
            return

        updated, installed_new, removed = 0, 0, 0
        for s, st in targets:
            if st in ("outdated", "available"):
                local = installed.get(s)
                dest_dir = Path(local.path).parent.parent if local else default_install_dir()
                try:
                    rec = _install_one(client, s, dest_dir)
                except PuyaApiError as e:
                    typer.echo(f"  ❌ {s}: {e}", err=True)
                    continue
                if st == "outdated":
                    updated += 1
                    typer.echo(f"  ⚠️  {s}: refreshed → hash={rec.content_hash}")
                else:
                    installed_new += 1
                    typer.echo(f"  🆕 {s}: installed → hash={rec.content_hash}")
            elif st == "orphan":
                local = installed[s]
                skill_dir = Path(local.path).parent
                try:
                    Path(local.path).unlink(missing_ok=True)
                    if skill_dir.exists() and not any(skill_dir.iterdir()):
                        skill_dir.rmdir()
                except OSError as e:
                    typer.echo(f"  ❌ {s}: no se pudo borrar — {e}", err=True)
                    continue
                remove_record(s)
                removed += 1
                typer.echo(f"  🗑️  {s}: removed (orphan)")

    parts = []
    if updated:
        parts.append(f"{updated} updated")
    if installed_new:
        parts.append(f"{installed_new} installed")
    if removed:
        parts.append(f"{removed} removed")
    typer.echo(f"done: {', '.join(parts) if parts else 'no changes'}")


# ───────────────────────────────────────────────────────────
# diff
# ───────────────────────────────────────────────────────────


@app.command("diff")
def diff_command(
    slug: Annotated[str, typer.Argument()],
    env: EnvOption = None,
) -> None:
    """Diff unified local vs remoto de una skill instalada."""
    installed = load_state()
    local = installed.get(slug)
    if not local:
        typer.echo(
            f"error: '{slug}' no está instalada localmente (puya skills list para ver)", err=True
        )
        raise typer.Exit(code=1)
    try:
        local_text = Path(local.path).read_text(encoding="utf-8")
    except OSError as e:
        typer.echo(f"error: no se pudo leer {local.path}: {e}", err=True)
        raise typer.Exit(code=1) from e

    with _client(env) as client:
        try:
            remote_text = fetch_skill_raw(client, slug)
        except PuyaApiError as e:
            typer.echo(f"error: {e}", err=True)
            raise typer.Exit(code=e.exit_code) from e

    local_hash = compute_hash(local_text)
    remote_hash = compute_hash(remote_text)
    if local_hash == remote_hash:
        typer.echo(f"no diff: local y remoto coinciden ({local_hash})")
        return

    diff = difflib.unified_diff(
        local_text.splitlines(keepends=True),
        remote_text.splitlines(keepends=True),
        fromfile=f"local/{slug}/SKILL.md ({local_hash})",
        tofile=f"remote/{slug}/SKILL.md ({remote_hash})",
        n=3,
    )
    sys.stdout.writelines(diff)


# ───────────────────────────────────────────────────────────
# uninstall
# ───────────────────────────────────────────────────────────


@app.command("uninstall")
def uninstall_command(
    slug: Annotated[str, typer.Argument()],
) -> None:
    """Borra la skill local (archivo + carpeta si queda vacía) y la remueve del state."""
    installed = load_state()
    local = installed.get(slug)
    if not local:
        typer.echo(f"'{slug}' no está instalada (state.json no la tiene)")
        raise typer.Exit(code=0)
    try:
        skill_path = Path(local.path)
        skill_path.unlink(missing_ok=True)
        skill_dir = skill_path.parent
        if skill_dir.exists() and not any(skill_dir.iterdir()):
            skill_dir.rmdir()
    except OSError as e:
        typer.echo(f"error: no se pudo borrar {local.path}: {e}", err=True)
        raise typer.Exit(code=1) from e
    remove_record(slug)
    typer.echo(f"🗑️  uninstalled {slug}")
