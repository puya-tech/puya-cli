"""Tests del retry built-in para GETs idempotentes.

Política: UN retry extra solo para GETs cuando hay RequestError o 5xx.
Las mutaciones (POST) nunca se reintentan — fin de la historia. Si el
server tiene dedupe sobre pending actions, eso es ortogonal: el cliente
no asume nada.
"""

from __future__ import annotations

import httpx
import pytest

from puya.lib.client import PuyaApiError, PuyaClient
from puya.lib.config import Config

CFG = Config(base_url="https://x.example", api_key="puya_x", target_env=None, timeout=5.0)


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """Skip time.sleep para que el suite siga siendo rápido."""
    monkeypatch.setattr("puya.lib.client.time.sleep", lambda _s: None)


def _client_with(handler) -> PuyaClient:
    transport = httpx.MockTransport(handler)
    client = PuyaClient(CFG)
    client._http = httpx.Client(base_url=CFG.base_url, transport=transport)
    return client


def test_get_500_then_200_retries_and_succeeds():
    """GET que devuelve 500 una vez se reintenta y triunfa en el segundo intento."""
    calls = []

    def handler(_req):
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(500, json={"error": "transient"})
        return httpx.Response(200, json={"ok": True})

    client = _client_with(handler)
    status, body = client.get("/api/cli-odoo/status")
    assert status == 200
    assert body == {"ok": True}
    assert len(calls) == 2


def test_get_500_twice_raises_after_retry():
    """GET que devuelve 500 las dos veces termina lanzando PuyaApiError."""
    calls = []

    def handler(_req):
        calls.append(1)
        return httpx.Response(503, json={"error": "still down"})

    client = _client_with(handler)
    with pytest.raises(PuyaApiError) as exc:
        client.get("/api/cli-odoo/status")
    assert exc.value.exit_code == 2
    assert len(calls) == 2


def test_post_500_does_NOT_retry():
    """POST nunca se reintenta — las mutaciones son exactly-once por construcción."""
    calls = []

    def handler(_req):
        calls.append(1)
        return httpx.Response(500, json={"error": "server error"})

    client = _client_with(handler)
    with pytest.raises(PuyaApiError) as exc:
        client.post("/api/cli-odoo/write", json={"model": "x", "ids": [1], "values": {}})
    assert exc.value.exit_code == 2
    assert len(calls) == 1


def test_get_request_error_then_success_retries():
    """RequestError (timeout/socket) en GET también dispara retry."""
    calls = []

    def handler(_req):
        calls.append(1)
        if len(calls) == 1:
            raise httpx.ConnectError("flaky network")
        return httpx.Response(200, json={"ok": True})

    client = _client_with(handler)
    status, body = client.get("/api/cli-odoo/status")
    assert status == 200
    assert len(calls) == 2


def test_get_request_error_twice_exits_2(monkeypatch):
    """Si ambas tentativas de GET dan RequestError, el cliente sale con exit 2."""

    def handler(_req):
        raise httpx.ConnectError("network down")

    client = _client_with(handler)
    with pytest.raises(SystemExit) as exc:
        client.get("/api/cli-odoo/status")
    assert exc.value.code == 2


def test_get_400_does_NOT_retry():
    """4xx en GET no es reintentable — es problema del input, no del server."""
    calls = []

    def handler(_req):
        calls.append(1)
        return httpx.Response(400, json={"error": "bad input"})

    client = _client_with(handler)
    with pytest.raises(PuyaApiError):
        client.get("/api/cli-odoo/status")
    assert len(calls) == 1
