"""Guard contra 2xx no-JSON tragado como dato.

Failure mode (relevamiento operativo Puyol, C4/C5): staging en cold-start
(o un proxy sirviendo su propio login/error con 200) devuelve una página
HTML con status 200. El cliente hacía `resp.json()` → ValueError →
`body = resp.text` (el HTML) → `resp.is_success` → devolvía (200, "<html>…")
y el agente trataba el HTML como respuesta válida.

El guard: un 2xx cuyo body no es JSON y no está vacío → PuyaApiError(502)
(exit 5 = server/red → retry-able). 204/empty sigue siendo éxito legítimo;
todos los endpoints con contenido devuelven JSON (incl. skills/raw, que
devuelve {"content": ...}).
"""

from __future__ import annotations

import httpx
import pytest

from puya.lib.client import PuyaApiError, PuyaClient
from puya.lib.config import Config

CFG = Config(base_url="https://x.example", api_key="puya_x", target_env=None, timeout=5.0)


def _client_with(handler) -> PuyaClient:
    transport = httpx.MockTransport(handler)
    client = PuyaClient(CFG)
    client._http = httpx.Client(base_url=CFG.base_url, transport=transport)
    return client


def test_200_html_no_se_traga_como_dato():
    """El caso central: 200 + HTML intersticial → error, no dato."""

    def handler(_req):
        return httpx.Response(
            200,
            text="<!DOCTYPE html><html><body>Application starting…</body></html>",
            headers={"content-type": "text/html; charset=utf-8"},
        )

    client = _client_with(handler)
    with pytest.raises(PuyaApiError) as exc:
        client.get("/api/cli-odoo/status")
    # 5 = server/red → el caller puede reintentar (cold-start es transitorio).
    assert exc.value.exit_code == 5
    assert "no-JSON" in str(exc.value)


def test_204_vacio_sigue_siendo_exito():
    """204 No Content (body vacío, no-JSON) NO debe disparar el guard."""

    def handler(_req):
        return httpx.Response(204)

    client = _client_with(handler)
    status, _body = client.post("/api/custom/something", json={})
    assert status == 204


def test_200_json_sigue_funcionando():
    """Sanity: 200 con JSON válido pasa igual que siempre."""

    def handler(_req):
        return httpx.Response(200, json={"ok": True, "records": [1, 2]})

    client = _client_with(handler)
    status, body = client.get("/api/cli-odoo/search")
    assert status == 200
    assert body["ok"] is True


def test_200_texto_plano_no_vacio_tambien_es_anomalia():
    """Un 2xx text/plain no vacío tampoco es un dato del contrato JSON."""

    def handler(_req):
        return httpx.Response(200, text="OK", headers={"content-type": "text/plain"})

    client = _client_with(handler)
    with pytest.raises(PuyaApiError) as exc:
        client.get("/api/cli-account/skills")
    assert exc.value.exit_code == 5
