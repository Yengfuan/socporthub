"""Small in-process scheduler for the single Railway web process."""

import asyncio
import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo

from api.config import get_settings
from api.database import SessionLocal
from api.models import DisposableRequest
from bot.notifications import notify_admins_todays_collections

logger = logging.getLogger(__name__)


async def collection_reminder_loop() -> None:
    last_notified: date | None = None
    while True:
        try:
            settings = get_settings()
            now = datetime.now(ZoneInfo(settings.app_timezone))
            if now.hour >= settings.collection_reminder_hour and last_notified != now.date():
                with SessionLocal() as db:
                    requests = (
                        db.query(DisposableRequest)
                        .filter(DisposableRequest.approved.is_(True), DisposableRequest.collection_date == now.date())
                        .all()
                    )
                    collections = [
                        (
                            r.proposal.title,
                            r.proposal.committee.name,
                            r.collection_time.strftime("%H:%M") if r.collection_time else "time not set",
                        )
                        for r in requests
                    ]
                await notify_admins_todays_collections(collections)
                last_notified = now.date()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Scheduled collection reminder failed")
        await asyncio.sleep(60 * 10)
