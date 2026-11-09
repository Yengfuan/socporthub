"""Vercel + Supabase deployment behaviour: cron endpoints, inline webhook, object storage
for posters and return photos, and the production settings guard."""

import asyncio
from contextlib import contextmanager
from datetime import datetime
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest

from api.config import Settings, get_settings
from api.database import get_db
from api.main import app
from api.models import BorrowRequest, BorrowStatus, Proposal, ScheduledJobRun
from api.routes import telegram_webhook
from api.services import scheduled_notifications as jobs
from api.services import storage
from tests.conftest import auth_header
from tests.test_proposals import ADMIN, USER_A, _approve_user, register


@pytest.fixture()
def settings(monkeypatch):
    """The cached app settings, with any attribute changes undone after the test."""
    current = get_settings()

    def set_(**values):
        for key, value in values.items():
            monkeypatch.setattr(current, key, value)
        return current

    return set_


class FakeStorage:
    def __init__(self):
        self.objects: dict[str, tuple[bytes, str]] = {}
        self.deleted: list[str] = []

    def install(self, monkeypatch):
        monkeypatch.setattr(storage, "upload", lambda path, data, ct: self.objects.__setitem__(path, (data, ct)))
        monkeypatch.setattr(storage, "download", lambda path: self.objects[path][0])
        monkeypatch.setattr(
            storage, "info",
            lambda path: {"size": len(self.objects[path][0]), "content_type": self.objects[path][1]} if path in self.objects else None,
        )
        monkeypatch.setattr(storage, "delete", lambda *paths: self.deleted.extend(p for p in paths if p))
        monkeypatch.setattr(storage, "signed_download_url", lambda path, expires_in=600: f"https://storage.test/sign/{path}")
        monkeypatch.setattr(storage, "signed_upload_url", lambda path: f"https://storage.test/upload/{path}")
        return self


@pytest.fixture()
def fake_storage(monkeypatch, settings):
    settings(storage_mode="supabase", supabase_url="https://x.supabase.co", supabase_service_role_key="k")
    return FakeStorage().install(monkeypatch)


def session():
    return contextmanager(app.dependency_overrides[get_db])()


def draft_proposal(client):
    register(client, ADMIN, "admin@example.com")
    _approve_user(client, USER_A, "a@example.com")
    draft = client.post(
        "/api/proposals", json={"title": "Poster event", "category": "event", "save_draft": True}, headers=auth_header(USER_A)
    )
    return draft.json()["id"]


# --- Settings ----------------------------------------------------------------------


def test_scheduler_runs_in_process_except_on_vercel():
    assert Settings(_env_file=None, vercel=False).run_inprocess_scheduler
    assert not Settings(_env_file=None, vercel=True).run_inprocess_scheduler
    assert Settings(_env_file=None, vercel=True, scheduler_mode="inprocess").run_inprocess_scheduler
    assert not Settings(_env_file=None, vercel=False, scheduler_mode="external").run_inprocess_scheduler


def test_production_guard_lists_unsafe_settings():
    assert Settings(_env_file=None, environment="development").production_problems() == []
    problems = " ".join(Settings(_env_file=None, environment="production", vercel=True, storage_mode="supabase").production_problems())
    for expected in ("SECRET_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_WEBHOOK_SECRET", "CRON_SECRET", "SUPABASE_URL"):
        assert expected in problems
    assert "CALENDAR_FEED_TOKEN" not in problems  # optional: prod serves the feed tokenless
    safe = Settings(
        _env_file=None,
        environment="production", vercel=True, secret_key="s", telegram_bot_token="t", telegram_webhook_secret="w",
        calendar_feed_token="c", cron_secret="cs", database_url="postgresql://u:p@h:6543/db",
        storage_mode="supabase", supabase_url="https://x.supabase.co", supabase_service_role_key="k",
    )
    assert safe.production_problems() == []


# --- Cron endpoints ----------------------------------------------------------------


def test_cron_endpoints_need_the_secret(client, settings, monkeypatch):
    tick = AsyncMock(return_value={})
    monkeypatch.setattr(jobs, "run_reminder_nudges_tick", tick)

    settings(cron_secret="")
    assert client.post("/api/cron/reminder-nudges").status_code == 503
    settings(cron_secret="s3cret")
    assert client.post("/api/cron/reminder-nudges").status_code == 401
    assert client.post("/api/cron/reminder-nudges", headers={"Authorization": "Bearer wrong"}).status_code == 401
    tick.assert_not_awaited()

    response = client.post("/api/cron/reminder-nudges", headers={"Authorization": "Bearer s3cret"})
    assert response.status_code == 200 and response.json()["ok"] is True
    tick.assert_awaited_once()


def test_cron_job_failure_is_a_500(client, settings, monkeypatch):
    settings(cron_secret="s3cret")
    monkeypatch.setattr(jobs, "run_borrow_reminders_tick", AsyncMock(side_effect=RuntimeError("boom")))
    response = client.get("/api/cron/borrow-reminders", headers={"Authorization": "Bearer s3cret"})
    assert response.status_code == 500


def test_collection_digest_sends_once_per_day(client, settings, monkeypatch):
    settings(collection_reminder_hour=8)
    with session() as db:
        monkeypatch.setattr(jobs, "SessionLocal", lambda: contextmanager(app.dependency_overrides[get_db])())
        notify = AsyncMock()
        monkeypatch.setattr(jobs, "notify_admins_todays_collections", notify)
        tz = ZoneInfo(get_settings().app_timezone)

        early = asyncio.run(jobs.run_collection_digest_tick(datetime(2026, 11, 10, 7, 0, tzinfo=tz)))
        assert early == {"skipped": "too early"}
        asyncio.run(jobs.run_collection_digest_tick(datetime(2026, 11, 10, 8, 5, tzinfo=tz)))
        again = asyncio.run(jobs.run_collection_digest_tick(datetime(2026, 11, 10, 9, 0, tzinfo=tz)))
        assert again == {"skipped": "already sent today"}
        asyncio.run(jobs.run_collection_digest_tick(datetime(2026, 11, 11, 8, 0, tzinfo=tz)))
        assert notify.await_count == 2
        assert db.get(ScheduledJobRun, jobs.COLLECTION_DIGEST_JOB).last_run_on.isoformat() == "2026-11-11"


def test_collection_digest_retries_when_the_send_fails(client, settings, monkeypatch):
    settings(collection_reminder_hour=8)
    monkeypatch.setattr(jobs, "SessionLocal", lambda: contextmanager(app.dependency_overrides[get_db])())
    monkeypatch.setattr(jobs, "notify_admins_todays_collections", AsyncMock(side_effect=RuntimeError("telegram down")))
    tz = ZoneInfo(get_settings().app_timezone)
    with pytest.raises(RuntimeError):
        asyncio.run(jobs.run_collection_digest_tick(datetime(2026, 11, 10, 8, 5, tzinfo=tz)))
    with session() as db:
        assert db.get(ScheduledJobRun, jobs.COLLECTION_DIGEST_JOB) is None


# --- Telegram webhook --------------------------------------------------------------


def test_webhook_handles_the_update_before_answering(client, settings, monkeypatch):
    settings(telegram_webhook_secret="hook")
    handled = AsyncMock()
    monkeypatch.setattr(telegram_webhook, "handle_update", handled)
    assert client.post("/api/telegram/webhook", json={"update_id": 1}).status_code == 401
    response = client.post(
        "/api/telegram/webhook", json={"update_id": 1}, headers={"X-Telegram-Bot-Api-Secret-Token": "hook"}
    )
    assert response.status_code == 200
    handled.assert_awaited_once_with({"update_id": 1})


def test_webhook_answers_200_even_when_handling_fails(client, settings, monkeypatch):
    settings(telegram_webhook_secret="")
    monkeypatch.setattr(telegram_webhook, "handle_update", AsyncMock(side_effect=RuntimeError("boom")))
    assert client.post("/api/telegram/webhook", json={"update_id": 2}).status_code == 200


# --- Posters in object storage -----------------------------------------------------


def test_direct_poster_upload_goes_to_storage(client, fake_storage):
    proposal_id = draft_proposal(client)
    ticket = client.post(
        f"/api/proposals/{proposal_id}/poster/upload-url",
        json={"filename": "big poster.png", "content_type": "image/png", "size": 8 * 1024 * 1024},
        headers=auth_header(USER_A),
    )
    assert ticket.status_code == 200
    path = ticket.json()["path"]
    assert path.startswith(f"posters/{proposal_id}/") and ticket.json()["upload_url"].endswith(path)

    # Confirming before the browser's PUT has landed is refused.
    early = client.post(f"/api/proposals/{proposal_id}/poster/confirm", json={"path": path, "filename": "big poster.png"},
                        headers=auth_header(USER_A))
    assert early.status_code == 400

    fake_storage.objects[path] = (b"png-bytes", "image/png")  # the browser PUT
    confirmed = client.post(f"/api/proposals/{proposal_id}/poster/confirm", json={"path": path, "filename": "big poster.png"},
                            headers=auth_header(USER_A))
    assert confirmed.status_code == 200 and confirmed.json()["poster_filename"] == "big poster.png"
    with session() as db:
        proposal = db.get(Proposal, proposal_id)
        assert proposal.poster_storage_path == path and proposal.poster_data is None

    viewed = client.get(f"/api/proposals/{proposal_id}/poster", headers=auth_header(ADMIN))
    assert viewed.status_code == 200
    assert viewed.json() == {"signed_url": f"https://storage.test/sign/{path}", "filename": "big poster.png", "content_type": "image/png"}


def test_confirm_rejects_paths_from_other_proposals_and_bad_files(client, fake_storage):
    proposal_id = draft_proposal(client)
    other = f"posters/{proposal_id + 1}/abc-x.png"
    fake_storage.objects[other] = (b"x", "image/png")
    response = client.post(f"/api/proposals/{proposal_id}/poster/confirm", json={"path": other, "filename": "x.png"},
                           headers=auth_header(USER_A))
    assert response.status_code == 400

    too_big = f"posters/{proposal_id}/abc-huge.png"
    fake_storage.objects[too_big] = (b"x" * (10 * 1024 * 1024 + 1), "image/png")
    response = client.post(f"/api/proposals/{proposal_id}/poster/confirm", json={"path": too_big, "filename": "huge.png"},
                           headers=auth_header(USER_A))
    assert response.status_code == 413 and too_big in fake_storage.deleted


def test_upload_url_checks_owner_type_and_size(client, fake_storage):
    proposal_id = draft_proposal(client)
    url = f"/api/proposals/{proposal_id}/poster/upload-url"
    assert client.post(url, json={"filename": "a.png", "content_type": "image/png", "size": 10},
                       headers=auth_header(ADMIN)).status_code == 403
    assert client.post(url, json={"filename": "a.txt", "content_type": "text/plain", "size": 10},
                       headers=auth_header(USER_A)).status_code == 400
    assert client.post(url, json={"filename": "a.png", "content_type": "image/png", "size": 11 * 1024 * 1024},
                       headers=auth_header(USER_A)).status_code == 413


def test_replacing_a_poster_deletes_the_old_object(client, fake_storage):
    proposal_id = draft_proposal(client)
    for name in ("one.png", "two.png"):
        client.post(f"/api/proposals/{proposal_id}/poster", files={"poster": (name, b"img", "image/png")},
                    headers=auth_header(USER_A))
    with session() as db:
        current = db.get(Proposal, proposal_id).poster_storage_path
    assert current.endswith("two.png")
    assert len(fake_storage.deleted) == 1 and fake_storage.deleted[0].endswith("one.png")


def test_database_mode_keeps_the_old_upload_path(client, settings):
    settings(storage_mode="database")
    proposal_id = draft_proposal(client)
    ticket = client.post(f"/api/proposals/{proposal_id}/poster/upload-url",
                         json={"filename": "a.png", "content_type": "image/png", "size": 10}, headers=auth_header(USER_A))
    assert ticket.status_code == 200 and ticket.json() == {"upload_url": None, "path": None}


# --- Return photos in object storage -----------------------------------------------


def test_return_photo_goes_to_storage_and_is_served_signed(client, fake_storage):
    from api.services import borrowing
    from api.models import User

    register(client, ADMIN, "admin@example.com")
    _approve_user(client, USER_A, "a@example.com")
    with session() as db:
        user = db.query(User).filter_by(telegram_id=USER_A).one()
        from datetime import date
        request = BorrowRequest(requester_cca="Block 2", requested_by=user.id, activity_name="Movie", tables=1,
                                borrow_date=date(2026, 11, 1), return_date=date(2026, 11, 2), status=BorrowStatus.approved)
        db.add(request)
        db.commit()
        borrowing.submit_return_proof(db, user, request.id, "file-1", "image/jpeg", b"jpeg")
        db.refresh(request)
        assert request.return_proof_storage_path.startswith(f"borrow-proofs/{request.id}/")
        assert request.return_proof_data is None
        request_id, path = request.id, request.return_proof_storage_path

    response = client.get(f"/api/borrow/{request_id}/proof", headers=auth_header(ADMIN))
    assert response.status_code == 200 and response.json()["signed_url"].endswith(path)
