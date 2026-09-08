# Social Port Hub — Coding Guidelines

See `SOCIAL-PORT-HUB.md` for the full product spec. This file covers conventions for working in this codebase.

## Scope note

This codebase currently implements **Phases 1–4** (Foundation + Core Proposals +
Calendar, Disposables, Email & Reminders): registration/auth, committees, the proposal lifecycle
(including a comment thread and an optional reason attached to status changes), an
in-app calendar, hall disposables requests/approval, admin email drafts/sending, and
reminders. The calendar is database-backed with a public iCalendar feed; do not reintroduce
Google Calendar dependencies.
Check `models.py` and `routes/` before referencing anything from later phases in the spec.

**Calendar deviates from the spec**: it does not use the Google Calendar API (that
requires a GCP billing account). Events are stored in our own `calendar_events` table
and exposed read-only via a public iCalendar feed (`routes/calendar.py:calendar_feed`)
that people can subscribe to from their own calendar app — see README "Calendar".
Don't reintroduce a Google Calendar dependency without checking this decision first.

## Stack

- Backend: FastAPI (sync SQLAlchemy 2.0, not async — simplest correct choice at ~100 users)
- DB: PostgreSQL via Alembic migrations (never hand-edit the schema; always add a migration)
- Bot: raw Telegram Bot API over `httpx` (no bot framework) — webhook-based, delivered as
  a route inside the same FastAPI app so Railway only runs one process
- Frontend: vanilla JS SPA served as static files by FastAPI, no build step

## Conventions

- All DB access goes through `api/models.py` SQLAlchemy models + a request-scoped session
  (`api/database.py:get_db`). No raw SQL in route handlers.
- Auth: every WebApp API request must pass Telegram `initData` for HMAC validation
  (`api/auth.py`). There is no separate password/session auth.
- Committee-scoped visibility is enforced in the route layer, not the frontend — a
  non-admin user's queries must always filter by their committee membership.
- Status transitions (`needs_action → in_review → submitted → finished`) are validated
  server-side in `routes/proposals.py`; don't trust a status value posted from the client.
- Telegram notifications are fire-and-forget (log and continue on failure) — never let a
  Telegram API error fail the underlying DB operation that triggered it.
- Environment variables are read once via `api/config.py` (pydantic-settings); don't call
  `os.environ` directly elsewhere.
