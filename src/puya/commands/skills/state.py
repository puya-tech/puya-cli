"""State manifest local de skills instaladas — JSON en ~/.puya/skills-state.json.

Trackea por slug: dónde se instaló, qué hash tenía cuando se instaló, y
cuándo. Permite a `puya skills check` comparar contra el remoto sin
re-hashear el archivo cada vez.

Si el archivo local fue movido/borrado manualmente fuera del CLI, el
state queda inconsistente — `check` lo detecta como 'orphan' y sugiere
re-install o uninstall.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

STATE_FILE = Path.home() / ".puya" / "skills-state.json"


@dataclass
class InstalledSkill:
    slug: str
    content_hash: str
    path: str
    installed_at: str


def _ensure_dir() -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)


def load_state() -> dict[str, InstalledSkill]:
    if not STATE_FILE.exists():
        return {}
    try:
        raw = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    out: dict[str, InstalledSkill] = {}
    for slug, data in raw.items():
        if isinstance(data, dict) and all(
            k in data for k in ("slug", "content_hash", "path", "installed_at")
        ):
            out[slug] = InstalledSkill(**data)
    return out


def save_state(state: dict[str, InstalledSkill]) -> None:
    _ensure_dir()
    serializable = {slug: asdict(s) for slug, s in state.items()}
    STATE_FILE.write_text(
        json.dumps(serializable, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def record_install(slug: str, path: Path, content: str) -> InstalledSkill:
    state = load_state()
    skill = InstalledSkill(
        slug=slug,
        content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest()[:12],
        path=str(path),
        installed_at=datetime.now(timezone.utc).isoformat(),
    )
    state[slug] = skill
    save_state(state)
    return skill


def remove_record(slug: str) -> bool:
    state = load_state()
    if slug not in state:
        return False
    del state[slug]
    save_state(state)
    return True


def compute_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]


def default_install_dir() -> Path:
    """Detecta directorio razonable para instalar skills.

    Orden de preferencia:
      1. ~/.claude/skills/ si existe (Claude Code).
      2. ~/.codex/skills/ si existe (Codex local).
      3. ~/.config/opencode/skills/ si existe (OpenCode).
      4. ~/.local/share/puya-skills/ (fallback genérico).

    Para destino explícito, usar --to. Cuando no hay nada que decida,
    el comando debe pedir confirmación o un --to obligatorio para no
    instalar en lugar inesperado.
    """
    candidates = [
        Path.home() / ".claude" / "skills",
        Path.home() / ".codex" / "skills",
        Path.home() / ".config" / "opencode" / "skills",
    ]
    for c in candidates:
        if c.exists():
            return c
    return Path.home() / ".local" / "share" / "puya-skills"
