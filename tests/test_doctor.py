"""Tests para `puya doctor`."""

from __future__ import annotations

import json

import httpx
from typer.testing import CliRunner

from puya.cli import app

runner = CliRunner()

PUYA_ENV_VARS = (
    "PUYA_BASE_URL",
    "PUYA_API_KEY",
    "PUYA_API_KEY_STAGING",
    "PUYA_API_KEY_PROD",
    "PUYA_TARGET_ENV",
)


def _clear_puya_env(monkeypatch):
    for name in PUYA_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def test_doctor_with_no_keys_reports_issue_and_exits_1(monkeypatch):
    _clear_puya_env(monkeypatch)
    result = runner.invoke(app, ["doctor", "--no-network"])
    assert result.exit_code == 1
    out = result.stdout + (result.stderr or "")
    assert "API key no seteada" in out
    assert "issues" in out


def test_doctor_with_good_staging_only_resolves(monkeypatch):
    _clear_puya_env(monkeypatch)
    monkeypatch.setenv("PUYA_API_KEY_STAGING", "puya_test_staging_key_xyz")

    result = runner.invoke(app, ["doctor", "--no-network", "-o", "json"])
    assert result.exit_code == 0, result.stdout

    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["resolution"]["target_env"] == "staging"
    assert payload["resolution"]["api_key_source"] == "PUYA_API_KEY_STAGING"
    assert payload["resolution"]["error"] is None
    assert payload["issues"] == []


def test_doctor_redacts_api_keys_in_output(monkeypatch):
    """La key plana no debe aparecer en stdout — solo redactada."""
    _clear_puya_env(monkeypatch)
    secret = "puya_SUPER_SECRET_NEVER_LEAK_THIS_abcd1234"
    monkeypatch.setenv("PUYA_API_KEY_STAGING", secret)

    result = runner.invoke(app, ["doctor", "--no-network"])
    assert result.exit_code == 0
    assert secret not in result.stdout
    # Forma esperada: puya_SUPE…1234
    assert "puya_SUPE" in result.stdout
    assert "1234" in result.stdout


def test_doctor_no_network_skips_http_call(monkeypatch):
    """--no-network NO debe ejecutar httpx.head."""
    _clear_puya_env(monkeypatch)
    monkeypatch.setenv("PUYA_API_KEY_STAGING", "puya_x")

    def boom(*_a, **_kw):
        raise AssertionError("doctor --no-network no debería tocar la red")

    monkeypatch.setattr(httpx, "head", boom)

    result = runner.invoke(app, ["doctor", "--no-network"])
    assert result.exit_code == 0
    assert "skipped" in result.stdout
