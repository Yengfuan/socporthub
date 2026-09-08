# Social Port Hub

Telegram Bot + WebApp for consolidating Raffles Hall committee management under the
Social Director. Full spec: [`SOCIAL-PORT-HUB.md`](./SOCIAL-PORT-HUB.md).

**Current status:** Phases 1–3 (Foundation + Core Proposals + Calendar & Disposables) —
registration/approval, committees, the proposal lifecycle with comments, an in-app
calendar with an iCalendar subscription feed, and hall disposables requests/approval.
Email sending and reminders (Phase 4) are not built yet.

The calendar deviates from the original spec: instead of the Google Calendar API (which
requires a GCP billing account), events live in our own database and are exposed via a
free, open **iCalendar (.ics) feed** that anyone can subscribe to from Google/Apple/
Outlook calendar apps — see "Calendar" below.

## Local development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in TELEGRAM_BOT_TOKEN, DATABASE_URL, ADMIN_TELEGRAM_IDS, SECRET_KEY

# Postgres must be running and DATABASE_URL pointing at it
alembic upgrade head

uvicorn api.main:app --reload
```

The webapp is served at `/` from static files in `webapp/`; the API lives under `/api`.
Health check: `GET /api/health`.

**Testing the webapp outside Telegram:** with `ENVIRONMENT=development` and no
`TELEGRAM_BOT_TOKEN` set, the frontend and `api/auth.py` fall back to a `dev_telegram_id`
identity so you can open `http://localhost:8000` directly in a browser. Set
`localStorage.dev_telegram_id` in devtools to switch identities (e.g. an ID listed in
`ADMIN_TELEGRAM_IDS` to see the admin dashboard). This bypass is hard-disabled the
moment `TELEGRAM_BOT_TOKEN` is set, so it can't leak into a real deploy.

## Telegram setup

1. Create a bot via [@BotFather](https://t.me/BotFather), grab `TELEGRAM_BOT_TOKEN`.
2. Set `TELEGRAM_WEBAPP_URL` to your deployed HTTPS URL (WebApp requires HTTPS; use a
   tunnel like `ngrok` for local testing).
3. Register the webhook once your app is deployed:
   ```bash
   curl -F "url=${TELEGRAM_WEBAPP_URL}/api/telegram/webhook" \
        -F "secret_token=${TELEGRAM_WEBHOOK_SECRET}" \
        "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook"
   ```
4. In BotFather, set the WebApp menu button (`/setmenubutton`) to `TELEGRAM_WEBAPP_URL`.
5. Add your own numeric Telegram user ID to `ADMIN_TELEGRAM_IDS` (comma-separated) so you
   land in the admin dashboard instead of the registration flow.

## Calendar

Events live entirely in our own Postgres table (`calendar_events`) — created, listed,
and filtered through the webapp only. There's no external calendar API, no GCP project,
and no cost.

For people who want hall events to show up in their own phone's calendar app, the app
also publishes a public **iCalendar feed** at `GET /api/calendar/feed.ics`, which Google
Calendar, Apple Calendar, and Outlook can all "subscribe to" natively (Settings → Add
calendar → From URL). Subscribed calendars are read-only and typically refresh every few
hours, not instantly — fine for a hall events calendar. The webapp's Calendar tab shows
a "Subscribe from your phone's calendar app" link with the URL, so nobody needs to know
this endpoint exists.

Set `CALENDAR_FEED_TOKEN` (any random string) to require it as a `?token=` query param
on that URL — this keeps the feed from being trivially guessable by outsiders, similar
to how Google Calendar's own "secret address in iCal format" works. Leave it blank to
serve the feed with no token (fine for local dev).

## Deployment (Railway)

1. New Railway project → add a PostgreSQL plugin → copy its `DATABASE_URL`.
2. Deploy this repo (Railway reads `Procfile`, which runs migrations then starts uvicorn).
3. Set all variables from `.env.example` in Railway's dashboard.
4. Point `TELEGRAM_WEBAPP_URL` at the Railway-issued domain and re-run the `setWebhook`
   step above.

## Project layout

```
api/       FastAPI app, models, routes, services (Telegram + Google Calendar)
bot/       Telegram webhook update handling (/start, /help) + outbound notifications
webapp/    Vanilla JS SPA (Telegram WebApp UI)
migrations/  Alembic
tests/     pytest
```
