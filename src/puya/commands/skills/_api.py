"""Cliente helpers para los endpoints /api/cli-account/skills*.

Pequeño wrapper sobre PuyaClient para centralizar shape de response y
errores específicos del dominio skills.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from puya.lib.client import PuyaApiError, PuyaClient


@dataclass
class RemoteSkill:
    slug: str
    name: str
    description: str
    content_hash: str


def fetch_remote_skills(client: PuyaClient) -> list[RemoteSkill]:
    """GET /api/cli-account/skills → lista normalizada."""
    _, body = client.get("/api/cli-account/skills")
    if not isinstance(body, dict) or "skills" not in body:
        return []
    out: list[RemoteSkill] = []
    for item in body["skills"]:
        if not isinstance(item, dict):
            continue
        out.append(
            RemoteSkill(
                slug=str(item.get("slug", "")),
                name=str(item.get("name", "")),
                description=str(item.get("description", "")),
                content_hash=str(item.get("content_hash", "")),
            )
        )
    return out


def fetch_skill_raw(client: PuyaClient, slug: str) -> str:
    """GET /api/cli-account/skills/<slug>/raw → markdown content del SKILL.md."""
    _, body = client.get(f"/api/cli-account/skills/{slug}/raw")
    if not isinstance(body, dict) or "content" not in body:
        raise PuyaApiError(500, {"error": "respuesta sin 'content'"})
    return str(body["content"])


def find_remote(skills: list[RemoteSkill], slug: str) -> RemoteSkill | None:
    for s in skills:
        if s.slug == slug:
            return s
    return None


def as_json_list(skills: list[RemoteSkill]) -> list[dict[str, Any]]:
    return [
        {
            "slug": s.slug,
            "name": s.name,
            "description": s.description,
            "content_hash": s.content_hash,
        }
        for s in skills
    ]
