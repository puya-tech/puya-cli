"""Tests para emit_hint() en el cliente HTTP.

emit_hint emite líneas <puya-hint key="...">JSON</puya-hint> a stderr
para que el wrapper del agente (auth-proxy Puyol, Inngest) pueda
correlacionar requests / capturar pending_id sin gastar tokens del LLM.

Casos cubiertos:
  - X-Request-Id en response → correlation_id hint
  - 202 con pending_id en body → pending_id hint
  - 200 sin headers especiales → ningún hint
"""

from __future__ import annotations

import httpx

from puya.lib.client import PuyaClient
from puya.lib.config import Config

CFG = Config(base_url="https://x.example", api_key="puya_x", target_env=None, timeout=5.0)


def _make_transport(*, status: int, body: dict | None = None, headers: dict | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status,
            json=body if body is not None else {},
            headers=headers or {},
        )

    return httpx.MockTransport(handler)


def test_correlation_id_hint_emitted_when_header_present(capsys):
    transport = _make_transport(
        status=200,
        body={"ok": True},
        headers={"x-request-id": "req_abc123"},
    )
    client = PuyaClient(CFG)
    client._http = httpx.Client(base_url=CFG.base_url, transport=transport)
    client.get("/api/cli-odoo/status")

    err = capsys.readouterr().err
    assert '<puya-hint key="correlation_id">"req_abc123"</puya-hint>' in err


def test_pending_id_hint_emitted_on_202(capsys):
    transport = _make_transport(
        status=202,
        body={"pending_id": 9999, "status": "pending_approval"},
    )
    client = PuyaClient(CFG)
    client._http = httpx.Client(base_url=CFG.base_url, transport=transport)
    client.post("/api/cli-odoo/write", json={"model": "x", "ids": [1], "values": {}})

    err = capsys.readouterr().err
    assert '<puya-hint key="pending_id">9999</puya-hint>' in err


def test_no_hints_when_response_has_no_signals(capsys):
    transport = _make_transport(status=200, body={"ok": True})
    client = PuyaClient(CFG)
    client._http = httpx.Client(base_url=CFG.base_url, transport=transport)
    client.get("/api/cli-odoo/status")

    err = capsys.readouterr().err
    assert "<puya-hint" not in err
