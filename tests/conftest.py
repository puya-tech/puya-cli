"""Fixtures comunes."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _credenciales_aisladas(tmp_path, monkeypatch):
    """Ningún test lee ni escribe la sesión real de `puya login` del equipo."""
    monkeypatch.setenv("PUYA_CONFIG_DIR", str(tmp_path / "puya-config"))
