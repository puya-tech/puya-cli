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
    # `confirm` fue removido: approvals son server-side (Slack del admin).
    assert "confirm" not in out


def test_confirm_command_no_longer_exists():
    """`puya odoo confirm 123` debe fallar con 'No such command'."""
    result = runner.invoke(app, ["odoo", "confirm", "123"])
    assert result.exit_code != 0
    out = result.stdout + (result.stderr or "")
    assert "No such command" in out or "confirm" in out


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
        (401, 4),
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


def test_schema_command_emits_valid_json_catalog():
    """`puya schema` debe emitir JSON parseable con el árbol completo."""
    import json

    result = runner.invoke(app, ["schema"])
    assert result.exit_code == 0

    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "1"
    assert payload["cli_version"] == __version__

    root = payload["command"]
    assert root["name"] == "puya"
    subs = root["subcommands"]
    for expected in ("account", "odoo", "schema", "skills", "tool", "version"):
        assert expected in subs, f"falta top-level: {expected}"

    odoo_subs = subs["odoo"]["subcommands"]
    for expected in (
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
    ):
        assert expected in odoo_subs, f"falta odoo subcommand: {expected}"
    # `confirm` fue removido en #17 — el schema no debería listarlo.
    assert "confirm" not in odoo_subs

    write = odoo_subs["write"]
    assert write["path"] == "puya odoo write"
    params_by_name = {p["name"]: p for p in write["params"]}
    assert params_by_name["model"]["kind"] == "argument"
    assert params_by_name["model"]["required"] is True
    assert params_by_name["values"]["kind"] == "option"
    assert params_by_name["values"]["required"] is True
    assert "--values" in params_by_name["values"]["flags"]


def test_schema_command_does_not_touch_network(monkeypatch):
    """schema debe ser puro offline — no debe hacer requests HTTP."""
    import httpx

    def boom(*_a, **_kw):
        raise AssertionError("schema no debería hacer requests HTTP")

    monkeypatch.setattr(httpx.Client, "request", boom)
    monkeypatch.delenv("PUYA_API_KEY", raising=False)
    monkeypatch.delenv("PUYA_API_KEY_STAGING", raising=False)
    monkeypatch.delenv("PUYA_API_KEY_PROD", raising=False)

    result = runner.invoke(app, ["schema"])
    assert result.exit_code == 0
    assert '"schema_version"' in result.stdout
