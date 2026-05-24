"""Cliente HTTP del CLI hacia puya-chat.

Wrapper fino sobre httpx con:
  - Bearer auth automático
  - Mapeo de exit codes:
      0 = OK (200/201/204)
      1 = error de input / RBAC (400, 403, 404, 409, 422, 429)
      2 = error externo / Odoo (500, 502, 504)
      3 = approval pendiente (202)
      4 = auth — key inválida / vencida / no autorizada (401)
  - Mensajes de error legibles

Cada comando del CLI invoca uno o más métodos de este cliente. El cliente
no conoce de RBAC ni de Odoo — eso lo decide puya-chat.
"""

from __future__ import annotations

import sys
import time
from typing import Any

import httpx

from puya.lib.config import Config
from puya.lib.output import emit_hint

# Retry de UN intento extra para GETs (idempotentes) cuando el server
# responde 5xx o el socket falla. NUNCA aplica a POST — las mutaciones
# son exactly-once por construcción (pueden crear pending action que
# después se aprueba).
_RETRY_DELAY_SECONDS = 1.0
_RETRYABLE_STATUS = (500, 502, 503, 504)


# Códigos HTTP → exit codes para callers (agentes / scripts).
# Diseño: que el caller pueda decidir remediación sin parsear strings.
#   exit 1: tu input/permiso es el problema → corregilo y reintentá.
#   exit 2: server lejano caído → reintentar más tarde / escalar.
#   exit 3: pending — esperar approval, NO retry.
#   exit 4: tu key es el problema → rotarla o re-materializarla (admin).
def _exit_code_for(status: int) -> int:
    if 200 <= status < 300:
        if status == 202:
            return 3
        return 0
    if status == 401:
        return 4
    if status in (400, 403, 404, 409, 422, 429):
        return 1
    if status in (500, 502, 503, 504):
        return 2
    return 1


class PuyaApiError(Exception):
    def __init__(self, status: int, body: Any):
        self.status = status
        self.body = body
        msg = str(body["error"]) if isinstance(body, dict) and "error" in body else f"HTTP {status}"
        super().__init__(msg)
        self.exit_code = _exit_code_for(status)


class PuyaClient:
    def __init__(self, cfg: Config, *, timeout: float | None = None):
        self.cfg = cfg
        headers: dict[str, str] = {"Authorization": f"Bearer {cfg.api_key}"}
        # Validación defensiva server-side: si el env elegido por el cliente
        # no matchea el target_env de la api_key, puya-chat responde 400.
        # Solo se manda cuando el cliente eligió un env explícito (no en
        # modo legacy single-key, donde target_env queda None).
        if cfg.target_env:
            headers["X-Puya-Requested-Env"] = cfg.target_env
        self._http = httpx.Client(
            base_url=cfg.base_url,
            timeout=timeout if timeout is not None else cfg.timeout,
            headers=headers,
        )

    def __enter__(self) -> PuyaClient:
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
        emita como JSON con exit 3.

        Reintenta UNA vez para GETs cuando hay RequestError o 5xx. Las
        mutaciones (POST) nunca se reintentan — el server crea pending
        actions con dedupe propia, pero el cliente no debe asumirlo.
        """
        is_idempotent = method.upper() == "GET"
        max_attempts = 2 if is_idempotent else 1

        resp: httpx.Response | None = None
        last_error: httpx.RequestError | None = None
        for attempt in range(max_attempts):
            if attempt > 0:
                time.sleep(_RETRY_DELAY_SECONDS)
            try:
                resp = self._http.request(method, path, json=json)
            except httpx.RequestError as e:
                last_error = e
                resp = None
                continue
            # 5xx en GET → un retry más (si todavía nos quedan attempts).
            if (
                is_idempotent
                and resp.status_code in _RETRYABLE_STATUS
                and attempt < max_attempts - 1
            ):
                continue
            break

        if resp is None:
            sys.stderr.write(f"error: no pude conectar a {self.cfg.base_url}: {last_error}\n")
            sys.exit(2)

        body: Any
        try:
            body = resp.json()
        except ValueError:
            body = resp.text

        # Hints laterales — stderr, no impactan stdout que ve el LLM.
        # El wrapper del agente (auth-proxy Puyol / Inngest) los strippea
        # antes de pasar el output al modelo. Ver lib/output.emit_hint.
        req_id = resp.headers.get("x-request-id")
        if req_id:
            emit_hint("correlation_id", req_id)
        if resp.status_code == 202 and isinstance(body, dict) and body.get("pending_id"):
            emit_hint("pending_id", body["pending_id"])

        if resp.status_code == 202:
            return resp.status_code, body
        if resp.is_success:
            return resp.status_code, body

        raise PuyaApiError(resp.status_code, body)

    def get(self, path: str) -> tuple[int, Any]:
        return self.request("GET", path)

    def post(self, path: str, json: dict | None = None) -> tuple[int, Any]:
        return self.request("POST", path, json=json)
