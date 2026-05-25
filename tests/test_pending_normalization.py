"""Tests de la defensa contra silent failure de approval-pending.

Bug atrapado en review por uso real (2026-05-24):

  - `puya odoo search -l 1500` (over threshold): server devolvía 202 +
    pending_id correctamente, pero search.py descartaba el status y
    emitía body.get("records", []) = [] → agente cree que no hay
    resultados cuando en realidad hay un pending de approval.

  - `puya tool call bulk-update`: server devolvía 200 (en vez de 202)
    aunque body decía status: "approval_required". CLI no se enteraba
    y agente asumía operación ejecutada.

Doble defensa:

  1. client.request() normaliza: si body tiene pending_id en cualquier
     2xx, trata el status como 202 (cubre endpoints server-side mal
     implementados).
  2. search/read/count/tool-call chequean status == 202 explícitamente
     y emiten exit 3 con body completo (no extraen "records").
"""

from __future__ import annotations

import httpx
import pytest
from typer.testing import CliRunner

from puya.cli import app
from puya.lib.client import PuyaClient
from puya.lib.config import Config

runner = CliRunner()


CFG = Config(base_url="https://x.example", api_key="puya_x", target_env=None, timeout=5.0)


def _client_with(handler) -> PuyaClient:
    transport = httpx.MockTransport(handler)
    client = PuyaClient(CFG)
    client._http = httpx.Client(base_url=CFG.base_url, transport=transport)
    return client


# ── client.request() normalización ────────────────────────────────────


def test_client_normaliza_200_con_pending_id_a_202():
    """Server endpoints inconsistentes que devuelven 200 + body de pending."""

    def handler(_req):
        return httpx.Response(200, json={"pending_id": 42, "status": "approval_required"})

    client = _client_with(handler)
    status, body = client.post("/api/custom/something", json={})
    assert status == 202
    assert body["pending_id"] == 42


def test_client_no_normaliza_si_no_hay_pending_id():
    """200 normal sin pending_id queda como 200."""

    def handler(_req):
        return httpx.Response(200, json={"ok": True, "records": []})

    client = _client_with(handler)
    status, _body = client.post("/api/cli-odoo/search", json={})
    assert status == 200


def test_client_no_normaliza_si_status_ya_es_202():
    """202 explícito del server queda en 202 (sin double-normalize)."""

    def handler(_req):
        return httpx.Response(202, json={"pending_id": 7})

    client = _client_with(handler)
    status, body = client.post("/api/cli-odoo/write", json={})
    assert status == 202
    assert body["pending_id"] == 7


# ── search/read/count: 202 → exit 3 ────────────────────────────────────


@pytest.fixture
def mock_proxy(monkeypatch):
    """Intercepta httpx.Client con respuestas canned por path."""
    responses: dict[str, tuple[int, dict]] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        status, body = responses.get(request.url.path, (200, {"ok": True}))
        return httpx.Response(status, json=body)

    transport = httpx.MockTransport(handler)
    original_init = httpx.Client.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = transport
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.Client, "__init__", patched_init)
    monkeypatch.setenv("PUYA_API_KEY_STAGING", "puya_test")
    monkeypatch.delenv("PUYA_API_KEY_PROD", raising=False)
    monkeypatch.delenv("PUYA_API_KEY", raising=False)
    monkeypatch.delenv("PUYA_TARGET_ENV", raising=False)
    return responses


def test_search_con_threshold_emite_pending_no_records_vacios(mock_proxy):
    """Cubre el bug del review: search over threshold devolvía [] silencioso."""
    mock_proxy["/api/cli-odoo/search"] = (
        202,
        {"pending_id": 99, "status": "approval_required", "limit": 1500, "threshold": 1000},
    )

    result = runner.invoke(app, ["odoo", "search", "res.partner", "-l", "1500", "-f", "id"])
    assert result.exit_code == 3
    # El body completo debe estar en stdout, NO un array vacío engañoso.
    assert "pending_id" in result.stdout
    assert "99" in result.stdout
    assert result.stdout.strip() != "[]"


def test_read_con_pending_emite_exit_3(mock_proxy):
    mock_proxy["/api/cli-odoo/read"] = (
        202,
        {"pending_id": 50, "status": "approval_required"},
    )

    result = runner.invoke(app, ["odoo", "read", "res.partner", "1,2,3"])
    assert result.exit_code == 3
    assert "pending_id" in result.stdout


def test_count_con_pending_emite_exit_3(mock_proxy):
    mock_proxy["/api/cli-odoo/count"] = (
        202,
        {"pending_id": 51, "status": "approval_required"},
    )

    result = runner.invoke(app, ["odoo", "count", "res.partner"])
    assert result.exit_code == 3


def test_search_normal_sigue_funcionando(mock_proxy):
    """Sanity: el happy path no se rompió."""
    mock_proxy["/api/cli-odoo/search"] = (200, {"records": [{"id": 1, "name": "X"}]})

    result = runner.invoke(app, ["odoo", "search", "res.partner", "-l", "5"])
    assert result.exit_code == 0
    assert '"id": 1' in result.stdout


# ── tool call: server 200 con pending_id → cliente lo trata como 202 ───


def test_tool_call_200_con_pending_id_emite_exit_3(mock_proxy):
    """Cubre el bug del bulk-update: server endpoint custom devuelve 200
    en vez de 202 cuando crea pending. Cliente normaliza."""
    mock_proxy["/api/custom/some-tool"] = (
        200,
        {"pending_id": 77, "status": "approval_required", "model": "res.partner"},
    )

    result = runner.invoke(app, ["tool", "call", "some-tool"])
    assert result.exit_code == 3
    assert "pending_id" in result.stdout
    assert "77" in result.stdout


def test_tool_call_200_normal_sigue_exit_0(mock_proxy):
    """Sanity: tool call con respuesta normal devuelve 0."""
    mock_proxy["/api/custom/some-tool"] = (200, {"result": "ok", "data": [1, 2]})

    result = runner.invoke(app, ["tool", "call", "some-tool"])
    assert result.exit_code == 0
    assert '"result": "ok"' in result.stdout
