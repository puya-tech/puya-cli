"""Tests de `puya odoo wait` y `--wait` en mutaciones.

El server (puya-chat) responde `GET /api/cli-odoo/pending/<id>?wait=N` como
long-poll: vuelve con `settled: true` cuando el pending se resolvió, o con
`settled: false` al vencer la espera. Acá lo simulamos con MockTransport.
"""

from __future__ import annotations

import json

import httpx
import pytest
from typer.testing import CliRunner

from puya.cli import app
from puya.commands.odoo import wait as wait_mod

runner = CliRunner()


@pytest.fixture
def proxy(monkeypatch):
    """Server falso: `script[path]` es la lista de respuestas que va devolviendo."""
    script: dict[str, list[tuple[int, dict]]] = {}
    urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        urls.append(str(request.url))
        queue = script.get(request.url.path, [])
        status, body = queue.pop(0) if len(queue) > 1 else (queue[0] if queue else (404, {}))
        return httpx.Response(status, json=body)

    transport = httpx.MockTransport(handler)
    original_init = httpx.Client.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = transport
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.Client, "__init__", patched_init)
    monkeypatch.setattr(wait_mod, "SERVER_ERROR_BACKOFF_SECONDS", 0)
    monkeypatch.setenv("PUYA_API_KEY_STAGING", "puya_test")
    monkeypatch.delenv("PUYA_API_KEY_PROD", raising=False)
    monkeypatch.delenv("PUYA_API_KEY", raising=False)
    monkeypatch.delenv("PUYA_TARGET_ENV", raising=False)
    return script, urls


def _lines(stdout: str) -> list[dict]:
    """Líneas JSON de una sola línea (las de `wait`); ignora el JSON indentado del write."""
    out = []
    for line in stdout.splitlines():
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            out.append(parsed)
    return out


def test_wait_repite_el_long_poll_hasta_que_se_resuelve(proxy):
    script, urls = proxy
    script["/api/cli-odoo/pending/552"] = [
        (200, {"id": 552, "settled": False, "outcome": "pending"}),
        (
            200,
            {"id": 552, "settled": True, "outcome": "executed", "execution": {"result": {"id": 9}}},
        ),
    ]
    result = runner.invoke(app, ["odoo", "wait", "552"])
    assert result.exit_code == 0
    assert _lines(result.stdout) == [
        {"id": 552, "settled": True, "outcome": "executed", "execution": {"result": {"id": 9}}}
    ]
    assert len(urls) == 2
    assert "wait=45" in urls[0]


def test_wait_varios_ids_una_linea_por_cada_uno(proxy):
    script, _ = proxy
    script["/api/cli-odoo/pending/1"] = [(200, {"id": 1, "settled": True, "outcome": "executed"})]
    script["/api/cli-odoo/pending/2"] = [
        (200, {"id": 2, "settled": True, "outcome": "failed", "error": {"message": "boom"}})
    ]
    result = runner.invoke(app, ["odoo", "wait", "1", "2"])
    assert result.exit_code == 1
    assert sorted(line["id"] for line in _lines(result.stdout)) == [1, 2]


@pytest.mark.parametrize("outcome", ["rejected", "cancelled", "expired", "failed"])
def test_wait_desenlace_no_ejecutado_sale_1(proxy, outcome):
    script, _ = proxy
    script["/api/cli-odoo/pending/7"] = [(200, {"id": 7, "settled": True, "outcome": outcome})]
    result = runner.invoke(app, ["odoo", "wait", "7"])
    assert result.exit_code == 1


def test_wait_timeout_sale_3(proxy, monkeypatch):
    script, _ = proxy
    script["/api/cli-odoo/pending/7"] = [(200, {"id": 7, "settled": False, "outcome": "pending"})]
    result = runner.invoke(app, ["odoo", "wait", "7", "--minutes", "0"])
    assert result.exit_code == 3
    assert _lines(result.stdout)[0]["outcome"] == "pending"


def test_wait_since_viaja_al_server(proxy):
    script, urls = proxy
    script["/api/cli-odoo/pending/7"] = [(200, {"id": 7, "settled": True, "outcome": "executed"})]
    result = runner.invoke(app, ["odoo", "wait", "7", "--since", "2026-10-21T17:20:00Z"])
    assert result.exit_code == 0
    assert "since=2026-10-21T17%3A20%3A00Z" in urls[0]


def test_wait_sobrevive_un_5xx(proxy):
    script, _ = proxy
    script["/api/cli-odoo/pending/7"] = [
        (503, {"error": "caído"}),
        (503, {"error": "caído"}),
        (200, {"id": 7, "settled": True, "outcome": "executed"}),
    ]
    result = runner.invoke(app, ["odoo", "wait", "7"])
    assert result.exit_code == 0


def test_wait_id_ajeno_no_corta_los_demas(proxy):
    script, _ = proxy
    script["/api/cli-odoo/pending/1"] = [(200, {"id": 1, "settled": True, "outcome": "executed"})]
    script["/api/cli-odoo/pending/2"] = [(403, {"error": "pending no pertenece a este consumer"})]
    result = runner.invoke(app, ["odoo", "wait", "1", "2"])
    assert result.exit_code == 1
    by_id = {line["id"]: line for line in _lines(result.stdout)}
    assert by_id[1]["outcome"] == "executed"
    assert by_id[2]["outcome"] == "error"


def test_write_con_wait_espera_el_desenlace(proxy):
    script, _ = proxy
    script["/api/cli-odoo/write"] = [(202, {"pending_id": 42, "status": "approval_required"})]
    script["/api/cli-odoo/pending/42"] = [(200, {"id": 42, "settled": True, "outcome": "executed"})]
    result = runner.invoke(
        app, ["odoo", "write", "res.partner", "1,2", "-v", '{"comment":"x"}', "-r", "t", "--wait"]
    )
    assert result.exit_code == 0
    assert _lines(result.stdout)[-1]["outcome"] == "executed"


def test_write_sin_wait_sale_3_y_sugiere_wait(proxy):
    script, urls = proxy
    script["/api/cli-odoo/write"] = [(202, {"pending_id": 42, "status": "approval_required"})]
    result = runner.invoke(
        app, ["odoo", "write", "res.partner", "1,2", "-v", '{"comment":"x"}', "-r", "t"]
    )
    assert result.exit_code == 3
    assert "puya odoo wait 42" in (result.stderr or "")
    assert not any("/pending/" in u for u in urls)
