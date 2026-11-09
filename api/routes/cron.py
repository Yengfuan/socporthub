"""Scheduled-job endpoints, called by Supabase pg_cron (see supabase/setup.sql).

Each request runs one tick and returns. Auth is `Authorization: Bearer <CRON_SECRET>`;
with no CRON_SECRET configured the endpoints are disabled. GET is accepted too so the
same routes work with Vercel Cron or a plain uptime pinger.
"""

import hmac
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, status

from api.config import get_settings
from api.services import scheduled_notifications as jobs

router = APIRouter(prefix="/api/cron", tags=["cron"])
logger = logging.getLogger(__name__)


def require_cron_secret(authorization: str | None = Header(None)) -> None:
    secret = get_settings().cron_secret
    if not secret:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Scheduled jobs are not configured")
    if not authorization or not hmac.compare_digest(authorization, f"Bearer {secret}"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid cron secret")


async def _run(name: str, tick) -> dict:
    try:
        return {"job": name, "ok": True, **(await tick() or {})}
    except Exception:
        # A 500 shows up in pg_net's response log and Vercel's logs; the next tick retries.
        logger.exception("Scheduled job %s failed", name)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"{name} failed")


@router.api_route("/grading", methods=["GET", "POST"], dependencies=[Depends(require_cron_secret)])
async def grading() -> dict:
    # The old loop retried Drive folder creation every 10th minute; keep that cadence.
    retry_drive = jobs.app_now().minute % 10 == 0
    return await _run("grading", lambda: jobs.run_grading_tick(retry_drive=retry_drive))


@router.api_route("/reminder-nudges", methods=["GET", "POST"], dependencies=[Depends(require_cron_secret)])
async def reminder_nudges() -> dict:
    return await _run("reminder-nudges", jobs.run_reminder_nudges_tick)


@router.api_route("/collection-digest", methods=["GET", "POST"], dependencies=[Depends(require_cron_secret)])
async def collection_digest() -> dict:
    return await _run("collection-digest", jobs.run_collection_digest_tick)


@router.api_route("/borrow-reminders", methods=["GET", "POST"], dependencies=[Depends(require_cron_secret)])
async def borrow_reminders() -> dict:
    return await _run("borrow-reminders", jobs.run_borrow_reminders_tick)
