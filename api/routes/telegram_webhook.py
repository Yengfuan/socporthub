import logging

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request, status

from api.config import get_settings
from bot.handlers import handle_update

router = APIRouter(prefix="/api/telegram", tags=["telegram"])
logger = logging.getLogger(__name__)


@router.post("/webhook")
async def webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_telegram_bot_api_secret_token: str | None = Header(None),
) -> dict:
    settings = get_settings()
    if settings.telegram_webhook_secret and x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid webhook secret")

    update = await request.json()
    background_tasks.add_task(handle_update, update)
    return {"ok": True}
