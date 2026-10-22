"""`puya login`: la persona entra con su Google y el CLI guarda un token.

Usa el mismo OAuth del conector MCP de puya-chat (`/api/mcp/oauth/*`): PKCE
con un callback local en `127.0.0.1` (RFC 8252). Sin navegador en este equipo
(`--no-browser`), la persona abre la URL en otro lado y pega la dirección a la
que llegó, aunque el navegador diga que no carga.

Los tokens quedan en `~/.config/puya/credentials.json` (permisos 600), uno por
entorno: `pmt_` (acceso, 30 días) y `pmr_` (refresco). Antes de vencer, el CLI
lo refresca solo. Las keys `puya_` en env vars ganan siempre: son de máquinas
y lo explícito no lo pisa una sesión guardada.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import json
import os
import secrets
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

# Margen para refrescar antes de que el access token venza.
REFRESH_MARGIN_S = 60
LOGIN_TIMEOUT_S = 300
TOKEN_PATH = "/api/mcp/oauth/token"
AUTHORIZE_PATH = "/api/mcp/oauth/authorize"


class LoginError(Exception):
    pass


# ── Archivo de credenciales ─────────────────────────────────────────────


def credentials_path() -> Path:
    base = os.environ.get("PUYA_CONFIG_DIR") or os.path.join(
        os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "puya"
    )
    return Path(base) / "credentials.json"


def _read() -> dict:
    try:
        data = json.loads(credentials_path().read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _write(data: dict) -> None:
    path = credentials_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    # 600 desde el primer byte: el archivo lleva tokens.
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


@dataclass(frozen=True, slots=True)
class Session:
    env: str
    base_url: str
    access_token: str
    refresh_token: str
    expires_at: float
    consumer: str | None = None


def save_session(s: Session) -> None:
    data = _read()
    data.setdefault("sessions", {})[s.env] = {
        "base_url": s.base_url,
        "access_token": s.access_token,
        "refresh_token": s.refresh_token,
        "expires_at": s.expires_at,
        "consumer": s.consumer,
    }
    _write(data)


def delete_session(env: str | None = None) -> list[str]:
    """Borra la sesión de un entorno, o todas. Devuelve los entornos borrados."""
    data = _read()
    sessions = data.get("sessions", {})
    gone = [e for e in list(sessions) if env is None or e == env]
    for e in gone:
        del sessions[e]
    if gone:
        _write(data)
    return gone


def stored_sessions(base_url: str) -> dict[str, Session]:
    """Sesiones guardadas para este servidor, por entorno."""
    out: dict[str, Session] = {}
    for env, raw in _read().get("sessions", {}).items():
        if not isinstance(raw, dict) or raw.get("base_url") != base_url:
            continue
        try:
            out[env] = Session(
                env=env,
                base_url=raw["base_url"],
                access_token=raw["access_token"],
                refresh_token=raw["refresh_token"],
                expires_at=float(raw["expires_at"]),
                consumer=raw.get("consumer"),
            )
        except (KeyError, TypeError, ValueError):
            continue
    return out


# ── Tokens ──────────────────────────────────────────────────────────────


def _token_request(base_url: str, form: dict[str, str]) -> dict:
    try:
        resp = httpx.post(f"{base_url}{TOKEN_PATH}", data=form, timeout=30.0)
    except httpx.RequestError as e:
        raise LoginError(f"no se pudo conectar a {base_url}: {e}") from e
    body = (
        resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
    )
    if resp.status_code != 200 or "access_token" not in body:
        raise LoginError(
            body.get("error_description") or body.get("error") or f"HTTP {resp.status_code}"
        )
    return body


def access_token_for(env: str, base_url: str) -> str | None:
    """Token vigente del entorno, refrescándolo si está por vencer.

    Si el servidor rechaza el refresco (sesión cerrada por un admin, acceso
    revocado, más de 30 días), borra la sesión y devuelve None: hay que volver
    a entrar con `puya login`.
    """
    s = stored_sessions(base_url).get(env)
    if s is None:
        return None
    if s.expires_at - time.time() > REFRESH_MARGIN_S:
        return s.access_token
    try:
        body = _token_request(
            base_url, {"grant_type": "refresh_token", "refresh_token": s.refresh_token}
        )
    except LoginError:
        delete_session(env)
        return None
    save_session(
        Session(
            env=env,
            base_url=base_url,
            access_token=body["access_token"],
            refresh_token=body.get("refresh_token", s.refresh_token),
            expires_at=time.time() + float(body.get("expires_in", 0)),
            consumer=s.consumer,
        )
    )
    return body["access_token"]


# ── Flujo de navegador ──────────────────────────────────────────────────


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    )
    return verifier, challenge


def authorize_url(
    base_url: str, redirect_uri: str, state: str, challenge: str, env: str | None
) -> str:
    params = {
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    if env:
        params["env"] = env
    return f"{base_url}{AUTHORIZE_PATH}?{urlencode(params)}"


def code_from_callback(url: str, expected_state: str) -> str:
    """Saca el code de la URL de vuelta (también la que pega la persona)."""
    q = parse_qs(urlparse(url.strip()).query)
    if q.get("state", [""])[0] != expected_state:
        raise LoginError(
            "la respuesta no corresponde a este login (state distinto); vuelve a correr puya login"
        )
    code = q.get("code", [""])[0]
    if not code:
        raise LoginError("la dirección no trae el código de autorización")
    return code


_DONE_HTML = (
    "<!doctype html><meta charset='utf-8'><title>puya login</title>"
    "<body style='font:16px system-ui;margin:3em'>"
    "<h1>Listo</h1><p>Ya puedes volver a la terminal y cerrar esta pestaña.</p></body>"
).encode()


def _callback_server() -> tuple[HTTPServer, dict[str, str]]:
    """Servidor en 127.0.0.1, puerto libre, que guarda la URL de vuelta del navegador."""
    got: dict[str, str] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if not self.path.startswith("/callback"):
                self.send_response(404)
                self.end_headers()
                return
            got["url"] = f"http://127.0.0.1{self.path}"
            self.send_response(200)
            self.send_header("content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(_DONE_HTML)

        def log_message(self, *_args) -> None:
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    server.timeout = 1.0
    return server, got


def _wait_for_callback(server: HTTPServer, got: dict[str, str], timeout_s: float) -> str:
    deadline = time.time() + timeout_s
    while "url" not in got and time.time() < deadline:
        server.handle_request()
    if "url" not in got:
        raise LoginError(
            "se acabó el tiempo esperando el navegador (5 min); vuelve a correr puya login"
        )
    return got["url"]


def login(
    base_url: str,
    env: str | None,
    *,
    open_browser: bool,
    show_url,
    ask_pasted_url,
) -> tuple[str, dict]:
    """Corre el login y devuelve (access_token, tokens). No guarda nada.

    `show_url(url)` muestra la URL (y abre el navegador si corresponde);
    `ask_pasted_url()` pide la dirección de vuelta en modo `--no-browser`.
    """
    verifier, challenge = _pkce()
    state = secrets.token_urlsafe(16)

    if open_browser:
        server, got = _callback_server()
        redirect_uri = f"http://127.0.0.1:{server.server_address[1]}/callback"
        try:
            show_url(authorize_url(base_url, redirect_uri, state, challenge, env))
            callback = _wait_for_callback(server, got, LOGIN_TIMEOUT_S)
        finally:
            with contextlib.suppress(Exception):
                server.server_close()
    else:
        # Puerto fijo e improbable: nadie escucha ahí; la persona copia la
        # dirección a la que llegó su navegador.
        redirect_uri = "http://127.0.0.1:8976/callback"
        show_url(authorize_url(base_url, redirect_uri, state, challenge, env))
        callback = ask_pasted_url()

    code = code_from_callback(callback, state)
    tokens = _token_request(
        base_url,
        {
            "grant_type": "authorization_code",
            "code": code,
            "code_verifier": verifier,
            "redirect_uri": redirect_uri,
        },
    )
    return tokens["access_token"], tokens


def start_browser(url: str) -> bool:
    """Abre el navegador en un hilo aparte (algunos backends bloquean)."""
    import webbrowser

    opened: dict[str, bool] = {}

    def run() -> None:
        try:
            opened["ok"] = webbrowser.open(url)
        except Exception:
            opened["ok"] = False

    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(timeout=5)
    return opened.get("ok", False)
