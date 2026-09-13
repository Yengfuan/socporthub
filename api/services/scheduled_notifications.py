"""Small in-process scheduler for the single Railway web process."""

import asyncio
import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo

from api.config import get_settings
from api.database import SessionLocal
from api.models import DisposableRequest, Portfolio
from api.portfolio import committee_portfolio
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
                        {
                            "title": r.proposal.title,
                            "committee": r.proposal.committee.name,
                            "time": r.collection_time.strftime("%H:%M") if r.collection_time else "time not set",
                            "portfolio": committee_portfolio(r.proposal.committee),
                            "plates": r.plates,
                            "cups": r.cups,
                            "bowls": r.bowls,
                            "forks": r.forks,
                            "spoons": r.spoons,
                        }
                        for r in requests
                    ]
                for portfolio in Portfolio:
                    portfolio_collections = [item for item in collections if item["portfolio"] == portfolio]
                    await notify_admins_todays_collections(portfolio_collections, portfolio)
                last_notified = now.date()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Scheduled collection reminder failed")
        await asyncio.sleep(60 * 10)
