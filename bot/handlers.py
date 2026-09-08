"""Handles incoming Telegram webhook updates (commands only, no WebApp interaction —
that goes through the REST API instead)."""

import logging

from api.config import get_settings
from api.services.telegram import send_message, webapp_open_markup

logger = logging.getLogger(__name__)

HELP_TEXT = (
    "<b>Social Port Hub</b>\n\n"
    "/start — Open the app\n"
    "/help — Show this message\n\n"
    "Use the app to submit event proposals, track their status, and manage your "
    "committee's activity."
)


async def handle_update(update: dict) -> None:
    message = update.get("message")
    if not message:
        return  # ignore non-message updates (e.g. callback_query) for now

    chat_id = message.get("chat", {}).get("id")
    text = (message.get("text") or "").strip()
    if chat_id is None:
        return

    if text.startswith("/start"):
        await _handle_start(chat_id)
    elif text.startswith("/help"):
        await send_message(chat_id, HELP_TEXT)


async def _handle_start(chat_id: int) -> None:
    settings = get_settings()
    if settings.telegram_webapp_url:
        await send_message(
            chat_id,
            "Welcome to Social Port Hub! Tap below to open the app.",
            reply_markup=webapp_open_markup(settings.telegram_webapp_url),
        )
    else:
        await send_message(chat_id, "Welcome to Social Port Hub! The app link isn't configured yet.")
