"""Tests de integración por categoría de payload.

NO test por comando — eso es ruido. Estos 3 verifican el contrato
HTTP que el cliente arma para las 3 formas distintas que el server
recibe: read (search/read), mutation (write/create/delete), call.

Si alguno de estos rompe → cambió el shape de payload entre cliente y
proxy. Vale más que 11 tests idénticos.
"""

from __future__ import annotations

import json as json_lib

import httpx
import pytest
from typer.testing import CliRunner

from puya.cli import app

runner = CliRunner()


@pytest.fixture
def mock_http(monkeypatch):
    """Intercepta todos los httpx.Client creados durante el test."""
    captured: list[httpx.Request] = []
    responses: dict[str, tuple[int, dict]] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        status, body = responses.get(request.url.path, (200, {"ok": True}))
        return httpx.Response(status, json=body)

    transport = httpx.MockTransport(handler)
    original_init = httpx.Client.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = transport
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.Client, "__init__", patched_init)

    # Env mínimo para que el cliente arranque.
    monkeypatch.setenv("PUYA_API_KEY_STAGING", "puya_test_key")
    monkeypatch.delenv("PUYA_API_KEY_PROD", raising=False)
    monkeypatch.delenv("PUYA_API_KEY", raising=False)
    monkeypatch.delenv("PUYA_TARGET_ENV", raising=False)

    return captured, responses


def test_search_envia_payload_correcto_a_proxy(mock_http):
    """`puya odoo search` → POST /api/cli-odoo/search con model/domain/fields/limit."""
    captured, responses = mock_http
    responses["/api/cli-odoo/search"] = (200, {"records": [{"id": 1, "name": "X"}]})

    result = runner.invoke(
        app,
        ["odoo", "search", "res.partner", "-d", '[["active","=",true]]', "-l", "10"],
    )
    assert result.exit_code == 0, result.stdout

    assert len(captured) == 1
    req = captured[0]
    assert req.url.path == "/api/cli-odoo/search"
    body = json_lib.loads(req.content)
    assert body["model"] == "res.partner"
    assert body["domain"] == [["active", "=", True]]
    assert body["limit"] == 10
    assert "fields" in body


def test_write_envia_payload_correcto_y_handles_202(mock_http):
    """`puya odoo write` → POST /api/cli-odoo/write con model/ids/values + exit 3 en 202."""
    captured, responses = mock_http
    responses["/api/cli-odoo/write"] = (202, {"pending_id": 42, "status": "approval_required"})

    result = runner.invoke(
        app,
        [
            "odoo",
            "write",
            "res.partner",
            "1,2",
            "-v",
            '{"comment": "foo"}',
            "-r",
            "test",
        ],
    )
    assert result.exit_code == 3, result.stdout

    assert len(captured) == 1
    req = captured[0]
    assert req.url.path == "/api/cli-odoo/write"
    body = json_lib.loads(req.content)
    assert body["model"] == "res.partner"
    assert body["ids"] == [1, 2]
    assert body["values"] == {"comment": "foo"}
    assert body["reason"] == "test"

    # El body de respuesta se imprime en stdout para que el agente parsee
    # pending_id sin perder info.
    assert "42" in result.stdout


def test_call_envia_payload_correcto(mock_http):
    """`puya odoo call` → POST /api/cli-odoo/call con method/args/kwargs."""
    captured, responses = mock_http
    responses["/api/cli-odoo/call"] = (202, {"pending_id": 99})

    result = runner.invoke(
        app,
        [
            "odoo",
            "call",
            "sale.order",
            "action_confirm",
            "--args",
            "[[101]]",
            "-r",
            "confirm test",
        ],
    )
    assert result.exit_code == 3, result.stdout

    assert len(captured) == 1
    req = captured[0]
    assert req.url.path == "/api/cli-odoo/call"
    body = json_lib.loads(req.content)
    assert body["model"] == "sale.order"
    assert body["method"] == "action_confirm"
    assert body["args"] == [[101]]
    assert body["ids"] == [101]  # extraído de args[0]
    assert body["reason"] == "confirm test"
