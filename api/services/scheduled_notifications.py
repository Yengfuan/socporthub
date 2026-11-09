"""Scheduled jobs. Each job is a single "tick" function that does one pass and returns.

On Vercel there is no long-lived process, so Supabase pg_cron calls the ticks through
the protected /api/cron/* endpoints (api/routes/cron.py, supabase/setup.sql). Locally,
or on any single long-running process, the *_loop wrappers below call the same ticks
on a timer (started from api/main.py when Settings.run_inprocess_scheduler is true).

Every tick must be safe to run more often than its cadence: receipts live in the
database (grading_notifications, reminder_nudges, borrow rows, scheduled_job_runs).
"""

import asyncio
import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo

from api.config import get_settings
from api.database import SessionLocal
from api.models import DisposableRequest, DisposableStatus, Proposal, ProposalStatus, ScheduledJobRun
from bot.notifications import notify_admins_todays_collections

logger = logging.getLogger(__name__)

COLLECTION_DIGEST_JOB = "collection_digest"


def app_now() -> datetime:
    return datetime.now(ZoneInfo(get_settings().app_timezone))


async def run_grading_tick(retry_drive: bool) -> dict:
    from api.services.grading import process_grading_notifications
    from api.services.google_drive import provision_evidence

    if not get_settings().grading_enabled:
        return {"skipped": "grading disabled"}
    retried = 0
    with SessionLocal() as db:
        await process_grading_notifications(db)
        if retry_drive:
            proposals = db.query(Proposal).filter(
                Proposal.status != ProposalStatus.draft,
                (Proposal.drive_ready.is_(False)) | (Proposal.drive_error.is_not(None)),
            ).all()
            for proposal in proposals:
                await provision_evidence(db, proposal.id)
                retried += 1
    return {"drive_retried": retried}


async def run_reminder_nudges_tick() -> dict:
    from api.services.reminder_broadcasts import process_reminder_nudges

    with SessionLocal() as db:
        await process_reminder_nudges(db)
    return {}


def _todays_collections(db, today: date) -> list[dict]:
    requests = (
        db.query(DisposableRequest)
        .filter(
            DisposableRequest.status == DisposableStatus.approved,
            DisposableRequest.collection_date == today,
        )
        .all()
    )
    return [
        {
            "title": r.activity_name,
            "cca": r.requester_cca,
            "requester": r.requester.telegram_username or r.requester.display_name or r.requester.email,
            "time": r.collection_time.strftime("%H:%M") if r.collection_time else "time not set",
            "plates": r.plates,
            "cups": r.cups,
            "bowls": r.bowls,
            "forks": r.forks,
            "spoons": r.spoons,
        }
        for r in requests
    ]


async def run_collection_digest_tick(now: datetime | None = None) -> dict:
    """Once a day, from COLLECTION_REMINDER_HOUR, tell admins today's disposable pickups.
    The receipt is written only after the send, so a failed send is retried next tick."""
    now = now or app_now()
    if now.hour < get_settings().collection_reminder_hour:
        return {"skipped": "too early"}
    today = now.date()
    with SessionLocal() as db:
        receipt = db.get(ScheduledJobRun, COLLECTION_DIGEST_JOB)
        if receipt and receipt.last_run_on == today:
            return {"skipped": "already sent today"}
        collections = _todays_collections(db, today)
        await notify_admins_todays_collections(collections)
        if receipt is None:
            receipt = ScheduledJobRun(job=COLLECTION_DIGEST_JOB)
            db.add(receipt)
        receipt.last_run_on = today
        db.commit()
    return {"collections": len(collections)}


async def run_borrow_reminders_tick(now: datetime | None = None) -> dict:
    """Return reminders for borrowed tables/cambro, after the same morning hour as the
    disposable digest so nobody is pinged at midnight; receipts are stored on each row."""
    from api.services.borrowing import process_borrow_reminders

    now = now or app_now()
    if now.hour < get_settings().collection_reminder_hour:
        return {"skipped": "too early"}
    with SessionLocal() as db:
        await process_borrow_reminders(db, now.date())
    return {}


# --- In-process loops (local dev / a single long-running server) ---------------------


async def _every(seconds: int, name: str, tick) -> None:
    while True:
        try:
            await tick()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("%s scheduler failed; will retry", name)
        await asyncio.sleep(seconds)


async def grading_loop() -> None:
    counter = {"tick": 0}

    async def tick():
        retry = counter["tick"] % 10 == 0
        counter["tick"] += 1
        await run_grading_tick(retry_drive=retry)

    await _every(60, "Grading", tick)


async def reminder_nudge_loop() -> None:
    await _every(60, "Reminder nudge", run_reminder_nudges_tick)


async def collection_reminder_loop() -> None:
    await _every(60 * 10, "Collection digest", run_collection_digest_tick)


async def borrow_reminder_loop() -> None:
    await _every(60 * 10, "Borrow reminder", run_borrow_reminders_tick)
