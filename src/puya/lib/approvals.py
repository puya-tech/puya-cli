"""Helpers para el flujo de aprobaciones (capa 2).

Encapsula:
- Construcción de details para mcp_pending_actions (incluyendo target_env)
- Notificación a Slack/Telegram cuando needs_approval
- Determinación de needs_approval según role + is_massive

Usado por commands/odoo/{write,create,delete,call}.py
"""

from __future__ import annotations

from puya.lib.audit import AuditLogger
from puya.lib.config import Config
from puya.lib.rbac import RBACEngine
from puya.lib.slack import SlackNotifier
from puya.lib.telegram import TelegramNotifier


def build_details(
    cfg: Config,
    *,
    fields: list[str] | None = None,
    method: str | None = None,
    reason: str | None = None,
    extra: dict | None = None,
) -> dict:
    """Arma el dict `details` que se guarda en mcp_pending_actions.

    Siempre incluye target_env / odoo_url / odoo_db (necesario para que
    approval-execute sepa contra qué entorno aplicar el write).
    """
    details: dict = {
        "target_env": cfg.environment,
        "odoo_url": cfg.odoo_url,
        "odoo_db": cfg.odoo_db,
    }
    if fields is not None:
        details["fields"] = fields
    if method is not None:
        details["method"] = method
    if reason is not None:
        details["reason"] = reason
    if extra:
        details.update(extra)
    return details


def needs_approval(rbac: RBACEngine, role: str, *, is_massive: bool) -> bool:
    return rbac.always_approve(role) or (is_massive and role != "developer")


def notify(
    cfg: Config,
    *,
    pending_id: int,
    user: str,
    role: str,
    action: str,
    model: str,
    record_count: int,
    preview: str,
    reason: str | None,
    audit: AuditLogger,
) -> tuple[str | int | None, str]:
    """Envía la solicitud de aprobación al canal configurado.

    Slack tiene precedencia si está configurado; Telegram como fallback.
    Devuelve (msg_id, channel_type). Persiste el msg_id en el pending
    para que el callback pueda actualizarlo después.
    """
    import os

    slack_token = os.environ.get("SLACK_BOT_TOKEN") or ""
    slack_channel = os.environ.get("SLACK_APPROVAL_CHANNEL") or ""
    tg_token = os.environ.get("TELEGRAM_BOT_TOKEN") or ""
    tg_chat = os.environ.get("TELEGRAM_CHAT_ID") or ""

    slack_notifier = SlackNotifier(bot_token=slack_token or None, channel=slack_channel or None)
    telegram = TelegramNotifier(bot_token=tg_token or None, chat_id=tg_chat or None)

    msg_id: str | int | None = None
    channel_type = "none"

    if slack_notifier.enabled:
        msg_id = slack_notifier.send_approval_request(
            pending_id=pending_id,
            user=user,
            role=role,
            action=action,
            model=model,
            record_count=record_count,
            preview=preview,
            reason=reason,
        )
        channel_type = "slack"
    elif telegram.enabled:
        msg_id = telegram.send_approval_request(
            pending_id=pending_id,
            user=user,
            role=role,
            action=action,
            model=model,
            record_count=record_count,
            preview=preview,
            reason=reason,
        )
        channel_type = "telegram"

    # update_pending_telegram_id solo aplica a Telegram (la columna es bigint y
    # Telegram devuelve int). Slack devuelve un ts string con decimal
    # (ej "1776952315.066299") — guardarlo ahí dispara HTTP 400. La
    # interactivity API de Slack incluye channel+ts en cada callback, así que
    # no necesitamos persistirlo nosotros para el flujo de approval.
    if msg_id is not None and channel_type == "telegram":
        import contextlib

        with contextlib.suppress(ValueError, TypeError):
            audit.update_pending_telegram_id(pending_id, int(msg_id))

    _ = cfg  # reservado para futura config (alert channel custom, etc.)
    return msg_id, channel_type
