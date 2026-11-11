import sys

from puya.commands import update


def test_uv_tool_reinstala_con_uv(monkeypatch):
    # El venv de `uv tool install` no trae pip: `python -m pip` falla.
    monkeypatch.setattr(sys, "prefix", "/home/x/.local/share/uv/tools/puya")
    monkeypatch.setattr(update.shutil, "which", lambda _: "/home/x/.local/bin/uv")
    assert update.install_command() == [
        "/home/x/.local/bin/uv",
        "tool",
        "install",
        "--force",
        update.REPO_URL,
    ]


def test_venv_o_pipx_sigue_con_pip(monkeypatch):
    monkeypatch.setattr(sys, "prefix", "/home/x/.local/pipx/venvs/puya")
    cmd = update.install_command()
    assert cmd[:3] == [sys.executable, "-m", "pip"]
    assert cmd[-1] == update.REPO_URL


def test_carpeta_tools_sin_uv_no_es_uv_tool():
    assert not update._es_uv_tool("/opt/tools/puya")
    assert update._es_uv_tool("/home/x/.local/share/uv/tools/puya")
