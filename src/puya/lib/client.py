"""Cliente HTTP del CLI hacia puya-chat.

Wrapper fino sobre httpx con:
  - Bearer auth automático
  - Mapeo de exit codes:
      0 = OK (200/201/204)
      1 = error de input (400, 403, 404, 409)
      2 = error externo / Odoo (500, 502, 504)
      3 = approval pendiente (202)
  - Mensajes de error legibles

Cada comando del CLI invoca uno o más métodos de este cliente. El cliente
no conoce de RBAC ni de Odoo — eso lo decide puya-chat.
"""

from __future__ import annotations

import sys
from typing import Any

import httpx

from puya.lib.config import Config


# Códigos HTTP → exit codes que matchea el contrato del CLI viejo (Puyol los usa)
def _exit_code_for(status: int) -> int:
    if 200 <= status < 300:
        # 202 = approval_required → exit 3
        if status == 202:
            return 3
        return 0
    if status in (400, 403, 404, 409, 422, 429):
        return 1
    if status in (401,):
        return 1
    if status in (500, 502, 503, 504):
        return 2
    return 1


class PuyaApiError(Exception):
    def __init__(self, status: int, body: Any):
        self.status = status
        self.body = body
        msg: str
        if isinstance(body, dict) and "error" in body:
            msg = str(body["error"])
        else:
            msg = f"HTTP {status}"
        super().__init__(msg)
        self.exit_code = _exit_code_for(status)


class PuyaClient:
    def __init__(self, cfg: Config, *, timeout: float = 30.0):
        self.cfg = cfg
        self._http = httpx.Client(
            base_url=cfg.base_url,
            timeout=timeout,
            headers={"Authorization": f"Bearer {cfg.api_key}"},
        )

    def __enter__(self) -> "PuyaClient":
        return self

    def __exit__(self, *_exc) -> None:
        self._http.close()

    def request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
    ) -> tuple[int, Any]:
        """Devuelve (status, body). Lanza PuyaApiError para 4xx/5xx, EXCEPTO
        202 que es approval_required y vuelve normal para que el caller lo
        emita como JSON con exit 3."""
        try:
            resp = self._http.request(method, path, json=json)
        except httpx.RequestError as e:
            sys.stderr.write(f"error: no pude conectar a {self.cfg.base_url}: {e}\n")
            sys.exit(2)

        body: Any
        try:
            body = resp.json()
        except ValueError:
            body = resp.text

        if resp.status_code == 202:
            return resp.status_code, body
        if resp.is_success:
            return resp.status_code, body

        raise PuyaApiError(resp.status_code, body)

    def get(self, path: str) -> tuple[int, Any]:
        return self.request("GET", path)

    def post(self, path: str, json: dict | None = None) -> tuple[int, Any]:
        return self.request("POST", path, json=json)
