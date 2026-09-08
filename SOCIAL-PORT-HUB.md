# Social Port Hub — Project Specification

> Telegram Bot + WebApp for consolidating Raffles Hall committee management under the Social Director.

---

## 1. Project Overview

A single platform for the Social Director (or successor) to manage event proposals, hall disposables requests, calendars, and communications across all RH committees. Users (committee members) submit proposals and requests; the admin reviews, approves, and tracks everything from one dashboard.

**Scale constraints:**
- 1 admin (or up to 11 committee-level admins)
- ~100 end users maximum
- No plans to scale beyond this

---

## 2. Architecture

### 2.1 Stack

| Layer | Tech | Notes |
|---|---|---|
| Interface | Telegram Bot + Telegram WebApp | Bot for notifications/reminders; WebApp for full UI |
| Frontend | Vanilla HTML/CSS/JS (or lightweight framework) | Served as Telegram WebApp; keep bundle small |
| Backend | Python (Flask or FastAPI) | REST API; FastAPI recommended for async + type hints |
| Database | PostgreSQL (Railway-managed) | Relational fits well — proposals, users, committees, requests |
| Hosting/CI/CD | Railway | One-click deploy from GitHub, managed Postgres addon |
| Email | Resend (free tier: 100 emails/day) | Draft generation + sending |
| Calendar | Google Calendar API | One shared calendar, events colour-coded per committee |
| File review | Google Docs API | Read-only access to linked docs for the AI reviewer (deferred) |

### 2.2 Architecture Assessment

The proposed stack is sufficient. Specific notes:

- **Database is missing from your list.** You need one. PostgreSQL on Railway is the simplest — it's a one-click addon on the same platform as your backend. SQLite could work at this scale but complicates Railway deploys (ephemeral filesystem).
- **Vercel vs Railway:** Pick one. Railway is better here — it runs Python natively, bundles Postgres, and you already used it for the check-in bot. Vercel is optimised for Node/edge and would need workarounds for Python (serverless functions with cold starts). **Recommendation: Railway only.**
- **Resend free tier** gives 100 emails/day and 1 custom domain. More than enough for this scale. You'll generate draft emails for users to copy-paste, so actual send volume is low.
- **Google Calendar API** requires a GCP project with Calendar API enabled. Use a service account that owns a single shared calendar. Events are colour-coded per committee using Google Calendar's `colorId` field. Share the calendar with committee members for read access in their own Google Calendar app.
- **Google Docs API** is only needed for the deferred AI reviewer. For now, users just paste a link.
- **Telegram WebApp auth** — Telegram provides `initData` with user identity, validated via HMAC. No separate auth system needed for Telegram users; the registration flow just maps a Telegram user to an approved email + committee.

### 2.3 System Diagram

```
┌─────────────────────────────────────────────────────┐
│                    Telegram                         │
│  ┌──────────┐    ┌────────────────────────────────┐ │
│  │   Bot    │    │         WebApp (UI)            │ │
│  │ (notifs) │    │  Landing · Calendar · Reminders│ │
│  └────┬─────┘    └──────────────┬─────────────────┘ │
└───────┼─────────────────────────┼───────────────────┘
        │                         │
        ▼                         ▼
┌─────────────────────────────────────────────────────┐
│              Python Backend (FastAPI)                │
│  /api/auth  /api/proposals  /api/disposables        │
│  /api/calendar  /api/reminders  /api/admin           │
├─────────────┬──────────────┬────────────────────────┤
│  PostgreSQL │ Google Cal   │  Resend                │
│  (Railway)  │ API          │  (email drafts)        │
└─────────────┴──────────────┴────────────────────────┘
```

---

## 3. Data Model

### 3.1 Tables

```sql
-- Users & access
users (
    id            SERIAL PRIMARY KEY,
    telegram_id   BIGINT UNIQUE NOT NULL,
    email         VARCHAR(255) UNIQUE NOT NULL,
    display_name  VARCHAR(100),
    role          VARCHAR(20) DEFAULT 'user',    -- 'user' | 'admin'
    status        VARCHAR(20) DEFAULT 'pending', -- 'pending' | 'approved' | 'rejected'
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

committees (
    id    SERIAL PRIMARY KEY,
    name  VARCHAR(100) UNIQUE NOT NULL,  -- 'Block 2', 'Soccom', etc.
    color VARCHAR(7) NOT NULL             -- hex colour for calendar events, e.g. '#E67C73'
);

user_committees (
    user_id      INT REFERENCES users(id),
    committee_id INT REFERENCES committees(id),
    PRIMARY KEY (user_id, committee_id)
);

-- Proposals
proposals (
    id            SERIAL PRIMARY KEY,
    committee_id  INT REFERENCES committees(id),
    submitted_by  INT REFERENCES users(id),
    title         VARCHAR(255) NOT NULL,
    description   TEXT,
    doc_link      TEXT,                          -- Google Docs / any URL
    status        VARCHAR(20) DEFAULT 'needs_action',
                  -- 'needs_action' | 'in_review' | 'submitted' | 'finished'
    event_date    DATE,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Hall disposables
disposable_requests (
    id            SERIAL PRIMARY KEY,
    proposal_id   INT REFERENCES proposals(id),  -- tied to a proposal
    requested_by  INT REFERENCES users(id),
    plates        INT DEFAULT 0,
    cups          INT DEFAULT 0,
    forks         INT DEFAULT 0,
    spoons        INT DEFAULT 0,
    collection_date DATE NOT NULL,
    approved      BOOLEAN DEFAULT FALSE,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Reminders
reminders (
    id            SERIAL PRIMARY KEY,
    from_user     INT REFERENCES users(id),
    message       TEXT NOT NULL,
    target_type   VARCHAR(20),  -- 'proposal' | 'disposable' | 'general'
    target_id     INT,          -- nullable FK to relevant entity
    is_read       BOOLEAN DEFAULT FALSE,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Email drafts (generated)
email_drafts (
    id            SERIAL PRIMARY KEY,
    proposal_id   INT REFERENCES proposals(id),
    recipient     VARCHAR(255),
    subject       VARCHAR(255),
    body          TEXT,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);
```

### 3.2 Seed Data — Committees

Pre-populate on first deploy:

```
Block 2, Block 3, Block 4, Block 5, Block 6, Block 7, Block 8, Intl Comm, Soccom
```

---

## 4. Feature Specification

### 4.1 Registration & Auth

| Step | Detail |
|---|---|
| 1 | User opens Telegram WebApp → backend validates `initData` HMAC |
| 2 | If `telegram_id` not in `users` table → show registration form |
| 3 | User inputs email → saved with `status = 'pending'` |
| 4 | Admin gets Telegram notification → approves/rejects in admin panel |
| 5 | On approval, admin assigns user to one or more committees |
| 6 | User gets Telegram message confirming access |

### 4.2 User Features

#### 4.2.1 Landing Page / Dashboard

- **Top section:** Status summary cards showing proposal counts by status:
  `[Needs Action] [In Review] [Submitted] [Finished]`
  Scoped to the user's committee(s).
- **Below:** Recent proposals list (most recent first), each showing title, status badge, event date, and submitter.
- Tapping a proposal opens its detail page.

#### 4.2.2 Proposal Submission

- Form fields: Title, Description, Event Date, Google Doc/Link (optional)
- On submit → `status = 'needs_action'`, admin notified via Telegram bot
- User can view and edit their own proposals while in `needs_action`

#### 4.2.3 Proposal Detail Page

- Full proposal info + status badge
- Disposables request section (if applicable):
  - Plates, Cups, Forks, Spoons quantity inputs
  - Collection date picker
  - Submit/edit disposables request
  - Shows approval status
- Email section (read-only for user):
  - Shows the auto-generated email draft that admin will send
  - User can preview but not edit or send
- Doc link (opens in external browser)
- Status timeline / history

#### 4.2.4 Calendar View

- Monthly calendar showing events from the shared Google Calendar
- Events colour-coded by committee
- User can add important dates (syncs to Google Calendar, tagged with their committee colour)
- Visual indicators for proposal event dates
- Filter by committee

#### 4.2.5 Committee Visibility

- Users can see all proposals from people in the same committee
- Read-only access to other members' submissions
- Own submissions are editable (when status allows)

#### 4.2.6 Reminders

- User can send a "nudge" to admin for any pending item
- Free-text message attached to a specific proposal or general
- Shows in admin dashboard as a notification badge

### 4.3 Admin Features

#### 4.3.1 Admin Dashboard

- **Committee selector:** Tabs or dropdown for each committee
  `[Block 2] [Block 3] ... [Intl Comm] [Soccom] [All]`
- **Per-committee view:**
  - Summary cards: proposal counts by status
  - Proposals list with status badges, sortable/filterable
  - Calendar for that committee's events
  - Pending disposable requests (highlighted on collection day)

#### 4.3.2 Proposal Management

- View full proposal details
- Change status: `needs_action → in_review → submitted → finished`
- Each status change triggers a Telegram notification to the submitter
- **Email send action:** Admin previews the auto-generated email draft, can edit it, then hits "Send & Submit". This:
  1. Sends the email from admin's configured email address to the user's registered email via Resend
  2. Automatically advances the proposal status to `submitted`
  3. Notifies the user via Telegram that their proposal has been submitted
- View/approve linked disposables request

#### 4.3.3 Disposables Dashboard

- Aggregated view of all approved disposable requests
- Grouped by collection date
- Today's collections highlighted at the top
- Total quantities per day (useful for procurement)

#### 4.3.4 User Management

- Approve/reject pending registrations
- Assign users to committees
- View all users per committee

#### 4.3.5 AI Proposal Reviewer [DEFERRED — LOW PRIORITY]

- Reads the linked Google Doc via Docs API
- Sends content to an LLM for review
- Generates suggested comments
- Admin vets each comment before posting back to the doc
- **Not in MVP. Requires separate LLM training/prompting work.**

### 4.4 Shared Features

#### 4.4.1 Navigation

Three tabs in the WebApp:
```
[ Home ]  [ Calendar ]  [ Reminders ]
```
- Home: Dashboard (user or admin variant based on role)
- Calendar: Committee calendar view
- Reminders: Sent (user) or received (admin) reminders

#### 4.4.2 Telegram Bot Commands

```
/start        — Opens WebApp or shows welcome message
/status       — Quick status of user's proposals (inline, no WebApp needed)
/remind       — Quick-send a reminder to admin
/help         — Usage guide
```

Admin-only:
```
/pending      — List of items needing action across all committees
/approve <id> — Quick-approve a disposable request
```

---

## 5. API Routes

```
Auth
  POST   /api/auth/validate          — Validate Telegram initData
  POST   /api/auth/register          — Submit registration (email)

Users (admin)
  GET    /api/admin/users             — List all users
  PATCH  /api/admin/users/:id         — Approve/reject, assign committee

Proposals
  GET    /api/proposals               — List (filtered by committee, status)
  POST   /api/proposals               — Create new proposal
  GET    /api/proposals/:id           — Detail view
  PATCH  /api/proposals/:id           — Edit proposal (user) or change status (admin)

Disposables
  POST   /api/disposables             — Submit disposable request
  GET    /api/disposables             — List (admin: all; user: own)
  PATCH  /api/disposables/:id         — Approve/reject (admin)
  GET    /api/disposables/today       — Today's approved collections (admin)

Calendar
  GET    /api/calendar                 — Fetch events from shared Google Calendar (filterable by committee colour)
  POST   /api/calendar                 — Add event (colour-coded by committee)

Reminders
  POST   /api/reminders               — Send reminder to admin
  GET    /api/reminders               — List reminders (admin)
  PATCH  /api/reminders/:id/read      — Mark as read

Email (admin)
  GET    /api/email/preview/:proposal_id — Generate/preview email draft
  PATCH  /api/email/preview/:proposal_id — Admin edits draft before sending
  POST   /api/email/send/:proposal_id    — Send email via Resend + advance status to 'submitted'
```

---

## 6. Email Flow

**Direction:** Admin → User (sent via Resend from admin's configured email).

**Trigger:** Admin clicks "Send & Submit" on a proposal in `in_review` status.

**What happens:**
1. Backend generates email from template (admin can edit before sending)
2. Resend sends from admin's verified email to user's registered email
3. Proposal status auto-advances to `submitted`
4. User gets Telegram notification

**Resend setup:** Requires a verified domain or single sender email (e.g. `welfare@raffleshall.sg` or admin's NUS email). Free tier supports 100 emails/day — more than enough.

```
Subject: [Committee Name] Event Proposal — {proposal.title}

Dear {user.display_name},

Your event proposal for {committee.name} has been reviewed and
submitted. Here is a summary:

Event: {proposal.title}
Date: {proposal.event_date}
Description: {proposal.description}

Supporting document: {proposal.doc_link}

{if disposables_request}
Hall disposables have been approved for collection
on {disposable.collection_date}:
  - Plates: {disposable.plates}
  - Cups: {disposable.cups}
  - Forks: {disposable.forks}
  - Spoons: {disposable.spoons}
{/if}

If you have any questions, feel free to reach out.

Best regards,
{admin.display_name}
Social Director, Raffles Hall
```

---

## 7. Notification Flow

| Trigger | Who gets notified | Channel |
|---|---|---|
| New proposal submitted | Admin | Telegram bot message |
| Status change on proposal | Submitter | Telegram bot message |
| Admin sends email (→ submitted) | Submitter | Resend email + Telegram bot message |
| Disposable request submitted | Admin | Telegram bot message |
| Disposable request approved | Submitter | Telegram bot message |
| User sends reminder | Admin | Telegram bot message + dashboard badge |
| New user registration | Admin | Telegram bot message |
| Collection day (morning of) | Admin | Telegram bot scheduled message |

---

## 8. UI Design Direction

**Goal:** Clean, modern, and clearly *not* AI slop.

- **Framework:** Vanilla JS + CSS custom properties. No heavy framework needed at this scale.
- **Type:** Inter or Geist Sans via Google Fonts — clean, neutral, not the serif/cream default.
- **Palette:** Derive from Raffles Hall branding if available; otherwise a restrained neutral base (white/slate) with one intentional accent colour for status badges and CTAs.
- **Status badges:** Colour-coded pills:
  - `needs_action` → amber/orange
  - `in_review` → blue
  - `submitted` → purple
  - `finished` → green
- **Layout:** Single-column, mobile-first (Telegram WebApp is phone-width). Cards for proposals, no heavy borders or shadows.
- **Navigation:** Bottom tab bar fixed to viewport — Home, Calendar, Reminders. Admin sees the same tabs but with admin-scoped content.
- **Empty states:** Helpful, not cute. "No proposals yet — submit one to get started."
- **Interactions:** Minimal animation. Tap feedback only. No scroll-triggered reveals.

---

## 9. Project Structure

```
social-port-hub/
├── CLAUDE.md                    # Coding guidelines for Claude Code
├── README.md
├── requirements.txt
├── Procfile                     # Railway entrypoint
├── .env.example
│
├── bot/
│   ├── __init__.py
│   ├── handlers.py              # Telegram bot command handlers
│   └── notifications.py         # Outbound notification logic
│
├── api/
│   ├── __init__.py
│   ├── main.py                  # FastAPI app factory
│   ├── auth.py                  # Telegram initData validation
│   ├── routes/
│   │   ├── proposals.py
│   │   ├── disposables.py
│   │   ├── calendar.py
│   │   ├── reminders.py
│   │   ├── email.py
│   │   ├── users.py
│   │   └── admin.py
│   ├── models.py                # SQLAlchemy models
│   ├── schemas.py               # Pydantic request/response schemas
│   └── services/
│       ├── google_calendar.py   # Google Calendar API wrapper
│       ├── resend_email.py      # Resend API wrapper
│       └── telegram.py          # Bot API helpers
│
├── webapp/
│   ├── index.html               # SPA entry point
│   ├── css/
│   │   └── styles.css
│   ├── js/
│   │   ├── app.js               # Router + init
│   │   ├── api.js               # Fetch wrapper
│   │   ├── pages/
│   │   │   ├── home.js
│   │   │   ├── calendar.js
│   │   │   ├── reminders.js
│   │   │   ├── proposal-detail.js
│   │   │   ├── register.js
│   │   │   └── admin-dashboard.js
│   │   └── components/
│   │       ├── nav.js
│   │       ├── status-badge.js
│   │       ├── proposal-card.js
│   │       └── disposable-form.js
│   └── assets/
│
├── migrations/                  # Alembic migrations
│   └── ...
│
└── tests/
    └── ...
```

---

## 10. Environment Variables

```bash
# Telegram
TELEGRAM_BOT_TOKEN=
TELEGRAM_WEBAPP_URL=          # Public URL of the webapp

# Database
DATABASE_URL=                 # Railway provides this

# Google
GOOGLE_SERVICE_ACCOUNT_JSON=  # Base64-encoded service account key
GOOGLE_CALENDAR_ID=           # Single shared calendar ID

# Resend
RESEND_API_KEY=
RESEND_FROM_EMAIL=              # Verified sender, e.g. welfare@raffleshall.sg

# App
ADMIN_TELEGRAM_IDS=           # Comma-separated Telegram user IDs for admin role
SECRET_KEY=                   # For session/HMAC
```

---

## 11. Implementation Phases

### Phase 1 — Foundation (MVP)
- [ ] Railway project setup + PostgreSQL
- [ ] FastAPI app skeleton with health check
- [ ] Telegram bot with `/start` that opens WebApp
- [ ] `initData` HMAC validation
- [ ] User registration flow (submit email → admin approves)
- [ ] Database models + Alembic migrations
- [ ] Seed committees

### Phase 2 — Core Proposals
- [ ] Proposal CRUD (create, list, detail, edit)
- [ ] Admin status management (change status on proposals)
- [ ] Telegram notifications on status change
- [ ] Committee-scoped visibility (users see their committee's proposals)
- [ ] Landing page dashboard with status summary cards

### Phase 3 — Calendar & Disposables
- [ ] Google Calendar API integration (service account)
- [ ] Calendar view in WebApp (read + add events)
- [ ] Disposable request form on proposal detail page
- [ ] Admin disposables dashboard with collection-day view
- [ ] Disposable approval flow

### Phase 4 — Email & Reminders
- [ ] Email draft auto-generation from proposal data
- [ ] Admin email preview + edit UI on proposal detail page
- [ ] Resend integration — admin sends email, proposal auto-advances to `submitted`
- [ ] Verified sender setup (domain or single sender email)
- [ ] Reminder system (user → admin nudges)
- [ ] Admin reminder inbox with badge count

### Phase 5 — Polish
- [ ] Admin committee tabs with per-committee filtering
- [ ] Bot inline commands (`/status`, `/pending`)
- [ ] Scheduled morning notification for today's disposable collections
- [ ] Empty states, loading states, error handling
- [ ] Mobile UI pass — test in actual Telegram WebApp

### Phase 6 — AI Reviewer [DEFERRED]
- [ ] Google Docs API read access
- [ ] LLM integration for proposal review
- [ ] Comment suggestion UI for admin vetting
- [ ] Post-approved comments back to Google Doc

---

## 12. Key Decisions — Resolved

1. **Framework** — FastAPI (async, auto OpenAPI docs, type hints).
2. **Google Calendar setup** — One shared calendar, colour-coded by committee.
3. **Sender email address** — New personal email address, verified as single sender in Resend.
4. **Admin granularity** — Single admin (Feng) for now. No committee-head sub-roles.
5. **Webapp hosting** — Serve static files from FastAPI on Railway (simplest), or GitHub Pages. Either works; Railway keeps everything in one deploy.

---

## 13. Reference

- [Telegram WebApp Docs](https://core.telegram.org/bots/webapps)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [Google Calendar API](https://developers.google.com/calendar/api)
- [Resend Docs](https://resend.com/docs)
- [Railway Docs](https://docs.railway.app/)
