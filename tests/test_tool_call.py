"""Tests del comando `puya tool call`.

Foco: el workaround client-side para 404 sin error body. Cuando Next.js
auto-404 sin pasar por código nuestro, el body de la respuesta viene
vacío y el CLI antes solo decía "HTTP 404". Ahora inyectamos un hint
apuntando a `puya tool list`.
"""

from __future__ import annotations

import httpx
import pytest
from typer.testing import CliRunner

from puya.cli import app

runner = CliRunner()


@pytest.fixture
def mock_http(monkeypatch):
    """Intercepta httpx.Client con respuestas canned por path."""
    responses: dict[str, tuple[int, dict | str]] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        status, body = responses.get(request.url.path, (200, {"ok": True}))
        if isinstance(body, str):
            return httpx.Response(status, content=body.encode())
        return httpx.Response(status, json=body)

    transport = httpx.MockTransport(handler)
    original_init = httpx.Client.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = transport
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.Client, "__init__", patched_init)
    monkeypatch.setenv("PUYA_API_KEY_STAGING", "puya_test_key")
    monkeypatch.delenv("PUYA_API_KEY_PROD", raising=False)
    monkeypatch.delenv("PUYA_API_KEY", raising=False)
    monkeypatch.delenv("PUYA_TARGET_ENV", raising=False)
    return responses


def test_call_404_sin_error_body_emite_hint_del_cliente(mock_http):
    """Simula Next.js auto-404 (body genérico, sin error field)."""
    mock_http["/api/custom/nonexistent-tool"] = (404, "Not Found")

    result = runner.invoke(app, ["tool", "call", "nonexistent-tool"])
    assert result.exit_code == 1
    err = (result.stderr or "") + (result.stdout or "")
    assert "nonexistent-tool" in err
    assert "puya tool list" in err


def test_call_404_con_error_body_del_server_no_pisa_hint(mock_http):
    """Si el server (post-PR puya-chat) devuelve JSON con error, mostramos ese."""
    mock_http["/api/custom/some-tool"] = (
        404,
        {"error": "tool 'some-tool' not found", "hint": "ver puya tool list"},
    )

    result = runner.invoke(app, ["tool", "call", "some-tool"])
    assert result.exit_code == 1
    err = (result.stderr or "") + (result.stdout or "")
    # El mensaje del server gana — el cliente NO inyecta su propio hint
    # porque el server ya dio uno útil.
    assert "tool 'some-tool' not found" in err
    # El hint del client-side workaround NO debe aparecer (porque el server
    # ya está dando contexto en `error` field).
    assert err.count("puya tool list") == 0


def test_call_200_funciona_normal(mock_http):
    """Sanity: el happy path sigue intacto."""
    mock_http["/api/custom/working-tool"] = (200, {"result": "ok", "data": [1, 2, 3]})

    result = runner.invoke(app, ["tool", "call", "working-tool"])
    assert result.exit_code == 0
    assert "result" in result.stdout
    assert "ok" in result.stdout
