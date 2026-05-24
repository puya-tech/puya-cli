"""Tests para PUYA_TIMEOUT / Config.timeout."""

from __future__ import annotations

import pytest

from puya.lib.client import PuyaClient
from puya.lib.config import DEFAULT_TIMEOUT, Config, load_config


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    for name in (
        "PUYA_BASE_URL",
        "PUYA_API_KEY",
        "PUYA_API_KEY_STAGING",
        "PUYA_API_KEY_PROD",
        "PUYA_TARGET_ENV",
        "PUYA_TIMEOUT",
    ):
        monkeypatch.delenv(name, raising=False)


def test_default_timeout_is_30_seconds():
    cfg = load_config()
    assert cfg.timeout == DEFAULT_TIMEOUT == 30.0


def test_puya_timeout_env_var_overrides_default(monkeypatch):
    monkeypatch.setenv("PUYA_TIMEOUT", "120")
    cfg = load_config()
    assert cfg.timeout == 120.0


def test_puya_timeout_accepts_float(monkeypatch):
    monkeypatch.setenv("PUYA_TIMEOUT", "2.5")
    cfg = load_config()
    assert cfg.timeout == 2.5


@pytest.mark.parametrize("bad", ["", "abc", "-5", "0", " "])
def test_puya_timeout_invalid_falls_back_to_default(monkeypatch, bad):
    monkeypatch.setenv("PUYA_TIMEOUT", bad)
    cfg = load_config()
    assert cfg.timeout == DEFAULT_TIMEOUT


def test_client_uses_config_timeout():
    cfg = Config(base_url="https://x.example", api_key="puya_x", target_env=None, timeout=7.5)
    with PuyaClient(cfg) as c:
        # httpx.Timeout exposes .connect/.read/.write/.pool — todos al mismo valor
        # cuando se pasa un escalar.
        assert c._http.timeout.read == 7.5


def test_client_explicit_timeout_overrides_config():
    cfg = Config(base_url="https://x.example", api_key="puya_x", target_env=None, timeout=30.0)
    with PuyaClient(cfg, timeout=1.0) as c:
        assert c._http.timeout.read == 1.0
