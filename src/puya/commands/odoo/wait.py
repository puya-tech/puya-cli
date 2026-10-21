"""`puya odoo wait <id> [<id>...]` — espera el desenlace de pendings propios.

Bloquea hasta que cada pending se resuelve y, a medida que pasa, imprime una
línea JSON por pending con su desenlace (`outcome`): executed (con el
resultado), failed (con el error; el aprobador puede reintentar), rejected,
cancelled o expired. Está pensado para que un agente lo deje corriendo en
background y se entere solo, sin que el humano tenga que avisarle.

Por debajo hace long-poll a `GET /api/cli-odoo/pending/<id>?wait=45`: no
gasta requests mientras nadie aprueba.

Exit codes:
  0  todos ejecutados
  1  alguno terminó distinto (failed, rejected, cancelled, expired)
  3  se acabó el tiempo y alguno sigue esperando aprobación
  1/4/5 como el resto del CLI si el proxy rechazó la consulta de algún id
        (su línea trae outcome=error)
"""

from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Annotated
from urllib.parse import urlencode

import typer

from puya.commands._helpers import EnvOption, setup_client
from puya.lib.client import PuyaApiError, PuyaClient

# Tope del long-poll del server (MAX_WAIT_SECONDS en puya-chat).
LONG_POLL_SECONDS = 45
# Margen sobre el long-poll para el timeout HTTP del cliente.
HTTP_TIMEOUT_SECONDS = LONG_POLL_SECONDS + 20
# Espera entre reintentos si el server responde 5xx a mitad de la espera.
SERVER_ERROR_BACKOFF_SECONDS = 5
DEFAULT_MINUTES = 30.0


def _wait_one(client: PuyaClient, pending_id: int, deadline: float, since: str | None) -> dict:
    """Long-poll de un pending hasta que se resuelve o vence `deadline`."""
    while True:
        remaining = deadline - time.monotonic()
        params: dict[str, str] = {"wait": str(max(1, min(LONG_POLL_SECONDS, int(remaining))))}
        if since:
            params["since"] = since
        try:
            _, body = client.get(f"/api/cli-odoo/pending/{pending_id}?{urlencode(params)}")
        except PuyaApiError as e:
            # Un 5xx suelto no debería matar una espera de media hora.
            if e.exit_code == 5 and time.monotonic() + SERVER_ERROR_BACKOFF_SECONDS < deadline:
                time.sleep(SERVER_ERROR_BACKOFF_SECONDS)
                continue
            raise
        if not isinstance(body, dict):
            raise PuyaApiError(502, {"error": "respuesta inesperada del proxy"})
        if body.get("settled") or time.monotonic() >= deadline - 1:
            return body
        if "settled" not in body:
            # Server sin long-poll: no martillarlo.
            time.sleep(SERVER_ERROR_BACKOFF_SECONDS)


def run_wait(env: str | None, pending_ids: list[int], minutes: float, since: str | None) -> int:
    """Espera los pendings, imprime una línea JSON por cada uno y devuelve el exit code."""
    _, client = setup_client(env=env, timeout=HTTP_TIMEOUT_SECONDS)
    deadline = time.monotonic() + minutes * 60
    outcomes: list[str] = []
    error_codes: list[int] = []

    def one(pid: int) -> dict:
        try:
            return _wait_one(client, pid, deadline, since)
        except PuyaApiError as e:
            # Un id ajeno o inexistente no corta la espera de los demás.
            error_codes.append(e.exit_code)
            return {"id": pid, "outcome": "error", "error": str(e)}

    with client, ThreadPoolExecutor(max_workers=min(len(pending_ids), 8)) as pool:
        for fut in as_completed([pool.submit(one, pid) for pid in pending_ids]):
            body = fut.result()
            outcomes.append(str(body.get("outcome", "pending")))
            sys.stdout.write(json.dumps(body, ensure_ascii=False, default=str) + "\n")
            sys.stdout.flush()

    if error_codes:
        return error_codes[0]
    if any(o == "pending" for o in outcomes):
        return 3
    if all(o == "executed" for o in outcomes):
        return 0
    return 1


def wait_command(
    pending_ids: Annotated[list[int], typer.Argument(help="IDs de los pendings a esperar")],
    minutes: Annotated[
        float,
        typer.Option("--minutes", "-m", help="Máximo de minutos a esperar"),
    ] = DEFAULT_MINUTES,
    since: Annotated[
        str | None,
        typer.Option(
            "--since",
            help="Ignorar un fallo anterior a esta fecha ISO (el error.at que ya viste) "
            "para esperar el reintento del aprobador.",
        ),
    ] = None,
    env: EnvOption = None,
) -> None:
    """Espera el desenlace de pendings (una línea JSON por cada uno)."""
    raise typer.Exit(code=run_wait(env, pending_ids, minutes, since))


def finish_mutation(status: int, body: object, wait: bool, env: str | None) -> None:
    """Cierre común de write/create/delete/call después de emitir el body.

    202 = quedó pendiente de aprobación. Con `--wait` espera el desenlace;
    si no, sale con 3 y sugiere cómo enterarse sin preguntarle al humano.
    """
    if status != 202:
        return
    pending_id = body.get("pending_id") if isinstance(body, dict) else None
    if wait and pending_id is not None:
        raise typer.Exit(code=run_wait(env, [int(pending_id)], DEFAULT_MINUTES, None))
    if pending_id is not None:
        typer.echo(
            f"nota: para enterarte del desenlace sin preguntar, corré `puya odoo wait {pending_id}` "
            "(en background) o repetí con --wait.",
            err=True,
        )
    raise typer.Exit(code=3)
