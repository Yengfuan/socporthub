import logging

from fastapi import APIRouter, Header, HTTPException, Request, status

from api.config import get_settings
from bot.handlers import handle_update

router = APIRouter(prefix="/api/telegram", tags=["telegram"])
logger = logging.getLogger(__name__)


@router.post("/webhook")
async def webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(None),
) -> dict:
    settings = get_settings()
    if settings.telegram_webhook_secret and x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid webhook secret")

    update = await request.json()
    # Handle the update before responding. On serverless (Vercel) work scheduled after the
    # response may be frozen or dropped, so a BackgroundTask is not safe there.
    try:
        await handle_update(update)
    except Exception:
        # Still answer 200: a non-2xx makes Telegram redeliver the same update repeatedly,
        # and replaying a half-applied update is worse than logging and moving on.
        logger.exception("Failed to handle Telegram update %s", update.get("update_id"))
    return {"ok": True}
