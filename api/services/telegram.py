"""Thin wrapper around the raw Telegram Bot API (send-message only)."""

import logging

import httpx

from api.config import get_settings

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}"


def _api_url(method: str) -> str:
    token = get_settings().telegram_bot_token
    return f"{TELEGRAM_API_BASE.format(token=token)}/{method}"


async def send_message(chat_id: int, text: str, reply_markup: dict | None = None) -> None:
    """Fire-and-forget notification send. Logs and swallows errors — a Telegram outage
    must never fail the DB operation that triggered the notification."""
    settings = get_settings()
    if not settings.telegram_bot_token:
        logger.info("No TELEGRAM_BOT_TOKEN configured; skipping message to %s: %s", chat_id, text)
        return

    payload: dict = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(_api_url("sendMessage"), json=payload)
            resp.raise_for_status()
    except httpx.HTTPError:
        logger.exception("Failed to send Telegram message to %s", chat_id)


def webapp_open_markup(url: str, label: str = "Open Social Port Hub") -> dict:
    return {"inline_keyboard": [[{"text": label, "web_app": {"url": url}}]]}
