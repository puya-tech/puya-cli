"""Smoke tests del entry-point CLI."""

from __future__ import annotations

from typer.testing import CliRunner

from puya import __version__
from puya.cli import app

runner = CliRunner()


def test_help_runs() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Puya Tech CLI" in result.stdout


def test_version_command() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_odoo_subcommand_help() -> None:
    result = runner.invoke(app, ["odoo", "--help"])
    assert result.exit_code == 0
    assert "search" in result.stdout
    assert "status" in result.stdout
