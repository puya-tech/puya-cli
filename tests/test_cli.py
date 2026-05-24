"""Smoke tests del CLI v1.0 (HTTP wrapper).

No pegamos a la red en tests — solo verificamos help, version y validación
de config faltante.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from puya import __version__
from puya.cli import app
from puya.lib.client import _exit_code_for
from puya.lib.config import Config, validate_config

runner = CliRunner()


def test_version_command():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_help_lists_odoo_subcommands():
    result = runner.invoke(app, ["odoo", "--help"])
    assert result.exit_code == 0
    out = result.stdout
    for cmd in [
        "status",
        "search",
        "read",
        "count",
        "fields",
        "write",
        "create",
        "delete",
        "call",
        "pending",
        "cancel",
    ]:
        assert cmd in out


def test_status_without_api_key_fails_with_exit_1(monkeypatch):
    monkeypatch.delenv("PUYA_API_KEY", raising=False)
    result = runner.invoke(app, ["odoo", "status"])
    assert result.exit_code == 1
    output = (result.stderr or "") + (result.stdout or "")
    assert "PUYA_API_KEY" in output


@pytest.mark.parametrize(
    "status,expected",
    [
        (200, 0),
        (201, 0),
        (202, 3),
        (400, 1),
        (401, 1),
        (403, 1),
        (404, 1),
        (409, 1),
        (429, 1),
        (500, 2),
        (502, 2),
        (504, 2),
    ],
)
def test_exit_code_mapping(status: int, expected: int):
    assert _exit_code_for(status) == expected


def test_validate_config_rejects_empty_key():
    err = validate_config(Config(base_url="https://x", api_key="", target_env=None))
    assert err and "PUYA_API_KEY" in err


def test_validate_config_rejects_invalid_prefix():
    err = validate_config(Config(base_url="https://x", api_key="not_a_puya_key", target_env=None))
    assert err and "puya_" in err


def test_validate_config_accepts_well_formed():
    err = validate_config(Config(base_url="https://x", api_key="puya_abc123", target_env=None))
    assert err is None
