"""Tests de `puya login`: sesión guardada, refresco y precedencia de credenciales."""

from __future__ import annotations

import os
import stat
import threading
import time
import urllib.request

import httpx
import pytest
from typer.testing import CliRunner

from puya.cli import app
from puya.lib import login as L
from puya.lib.config import load_config, validate_config

BASE = "https://puya.example"
runner = CliRunner()


@pytest.fixture(autouse=True)
def _sin_env_vars(monkeypatch):
    for name in ("PUYA_API_KEY", "PUYA_API_KEY_STAGING", "PUYA_API_KEY_PROD", "PUYA_TARGET_ENV"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("PUYA_BASE_URL", BASE)


def _guardar(env: str, *, expira_en: float = 3600, access: str = "pmt_viejo") -> None:
    L.save_session(
        L.Session(
            env=env,
            base_url=BASE,
            access_token=access,
            refresh_token="pmr_x",
            expires_at=time.time() + expira_en,
            consumer="Ana",
        )
    )


def test_archivo_de_credenciales_con_permisos_600():
    _guardar("staging")
    mode = stat.S_IMODE(os.stat(L.credentials_path()).st_mode)
    assert mode == 0o600


def test_sesion_de_otro_servidor_no_se_usa():
    _guardar("staging")
    assert L.stored_sessions("https://otro.example") == {}
    assert set(L.stored_sessions(BASE)) == {"staging"}


def test_load_config_usa_la_sesion_cuando_no_hay_env_vars():
    _guardar("production", access="pmt_prod")
    cfg = load_config()
    assert (cfg.api_key, cfg.target_env, cfg.source) == ("pmt_prod", "production", "puya login")
    assert validate_config(cfg) is None


def test_env_var_gana_sobre_la_sesion(monkeypatch):
    _guardar("production", access="pmt_prod")
    monkeypatch.setenv("PUYA_API_KEY_PROD", "puya_maquina")
    cfg = load_config(env_override="production")
    assert (cfg.api_key, cfg.source) == ("puya_maquina", "PUYA_API_KEY_PROD")


def test_dos_sesiones_sin_env_pide_elegir():
    _guardar("production", access="pmt_prod")
    _guardar("staging", access="pmt_stg")
    assert load_config().api_key == ""
    assert load_config(env_override="staging").api_key == "pmt_stg"


def test_refresca_cuando_esta_por_vencer(monkeypatch):
    _guardar("staging", expira_en=10)
    pedidos = []

    def fake_post(url, data, timeout):
        pedidos.append((url, data))
        return httpx.Response(
            200,
            json={"access_token": "pmt_nuevo", "refresh_token": "pmr_nuevo", "expires_in": 3600},
        )

    monkeypatch.setattr(L.httpx, "post", fake_post)
    assert L.access_token_for("staging", BASE) == "pmt_nuevo"
    assert pedidos[0][0] == f"{BASE}/api/mcp/oauth/token"
    assert pedidos[0][1] == {"grant_type": "refresh_token", "refresh_token": "pmr_x"}
    assert L.stored_sessions(BASE)["staging"].refresh_token == "pmr_nuevo"


def test_refresco_rechazado_borra_la_sesion(monkeypatch):
    _guardar("staging", expira_en=10)
    monkeypatch.setattr(
        L.httpx,
        "post",
        lambda *a, **k: httpx.Response(
            400, json={"error": "invalid_grant", "error_description": "sesión cerrada"}
        ),
    )
    assert L.access_token_for("staging", BASE) is None
    assert L.stored_sessions(BASE) == {}
    err = validate_config(load_config(env_override="staging"), env_override="staging")
    assert err and "puya login --env staging" in err


def test_code_from_callback_exige_el_mismo_state():
    url = "http://127.0.0.1:8976/callback?code=pmc_abc&state=s1"
    assert L.code_from_callback(url, "s1") == "pmc_abc"
    with pytest.raises(L.LoginError):
        L.code_from_callback(url, "otro")
    with pytest.raises(L.LoginError):
        L.code_from_callback("http://127.0.0.1:8976/callback?state=s1&error=access_denied", "s1")


def test_authorize_url_lleva_pkce_y_env():
    url = L.authorize_url(BASE, "http://127.0.0.1:5000/callback", "s", "chal", "staging")
    assert url.startswith(f"{BASE}/api/mcp/oauth/authorize?")
    for parte in ("code_challenge=chal", "code_challenge_method=S256", "env=staging", "state=s"):
        assert parte in url


def test_login_completo_con_callback_local(monkeypatch):
    """El navegador vuelve al servidor local; el CLI canjea el code con el verifier."""
    canjes = []

    def fake_post(url, data, timeout):
        canjes.append(data)
        return httpx.Response(
            200, json={"access_token": "pmt_a", "refresh_token": "pmr_a", "expires_in": 3600}
        )

    monkeypatch.setattr(L.httpx, "post", fake_post)

    def navegador(url: str) -> None:
        q = dict(p.split("=", 1) for p in url.split("?", 1)[1].split("&"))
        redirect = urllib.request.unquote(q["redirect_uri"])
        vuelta = f"{redirect}?code=pmc_1&state={q['state']}"
        threading.Thread(target=lambda: urllib.request.urlopen(vuelta, timeout=5).read()).start()

    access, tokens = L.login(
        BASE, None, open_browser=True, show_url=navegador, ask_pasted_url=lambda: ""
    )
    assert access == "pmt_a" and tokens["refresh_token"] == "pmr_a"
    assert canjes[0]["grant_type"] == "authorization_code"
    assert canjes[0]["code"] == "pmc_1"
    assert canjes[0]["redirect_uri"].startswith("http://127.0.0.1:")
    assert len(canjes[0]["code_verifier"]) >= 43


def test_logout_borra_y_avisa():
    _guardar("staging")
    result = runner.invoke(app, ["logout"])
    assert result.exit_code == 0
    assert L.stored_sessions(BASE) == {}
