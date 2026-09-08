from tests.conftest import auth_header

ADMIN = 999
USER_A = 1001


def register(client, telegram_id, email):
    return client.post(
        "/api/auth/register",
        json={"email": email, "display_name": email.split("@")[0]},
        headers=auth_header(telegram_id),
    )


def _approve_user(client, telegram_id, email, committee_index=0):
    register(client, telegram_id, email)
    users = client.get("/api/admin/users", headers=auth_header(ADMIN)).json()
    user_id = next(u["id"] for u in users if u["telegram_id"] == telegram_id)
    committees = client.get("/api/committees", headers=auth_header(ADMIN)).json()
    client.patch(
        f"/api/admin/users/{user_id}",
        json={"status": "approved", "committee_ids": [committees[committee_index]["id"]]},
        headers=auth_header(ADMIN),
    )
    return user_id


def _create_proposal(client, telegram_id, title="Movie Night"):
    resp = client.post("/api/proposals", json={"title": title}, headers=auth_header(telegram_id))
    return resp.json()["id"]


def test_comment_thread_and_status_change_reason(client):
    register(client, ADMIN, "admin@example.com")
    _approve_user(client, USER_A, "a@example.com")
    proposal_id = _create_proposal(client, USER_A)

    # General comment, either party can post.
    post = client.post(
        f"/api/proposals/{proposal_id}/comments",
        json={"body": "Looks good, reviewing now"},
        headers=auth_header(ADMIN),
    )
    assert post.status_code == 201
    assert post.json()["author_name"] == "admin"

    comments = client.get(f"/api/proposals/{proposal_id}/comments", headers=auth_header(USER_A)).json()
    assert len(comments) == 1

    # Move to in_review, then send back with a reason attached.
    client.patch(f"/api/proposals/{proposal_id}", json={"status": "in_review"}, headers=auth_header(ADMIN))
    revert = client.patch(
        f"/api/proposals/{proposal_id}",
        json={"status": "needs_action", "comment": "Please add a budget breakdown"},
        headers=auth_header(ADMIN),
    )
    assert revert.status_code == 200
    assert revert.json()["status"] == "needs_action"

    comments = client.get(f"/api/proposals/{proposal_id}/comments", headers=auth_header(USER_A)).json()
    assert len(comments) == 2
    assert "budget breakdown" in comments[-1]["body"]


def test_disposable_request_lifecycle(client):
    register(client, ADMIN, "admin@example.com")
    _approve_user(client, USER_A, "a@example.com")
    proposal_id = _create_proposal(client, USER_A)

    create = client.post(
        f"/api/disposables/{proposal_id}",
        json={"plates": 20, "cups": 20, "forks": 0, "spoons": 0, "collection_date": "2026-12-01"},
        headers=auth_header(USER_A),
    )
    assert create.status_code == 201
    assert create.json()["approved"] is False
    disposable_id = create.json()["id"]

    # Non-admin can't approve.
    forbidden = client.patch(
        f"/api/disposables/{disposable_id}", json={"approved": True}, headers=auth_header(USER_A)
    )
    assert forbidden.status_code == 403

    approve = client.patch(
        f"/api/disposables/{disposable_id}", json={"approved": True}, headers=auth_header(ADMIN)
    )
    assert approve.status_code == 200
    assert approve.json()["approved"] is True

    # Once approved, owner editing is blocked.
    edit_blocked = client.post(
        f"/api/disposables/{proposal_id}",
        json={"plates": 99, "cups": 0, "forks": 0, "spoons": 0, "collection_date": "2026-12-01"},
        headers=auth_header(USER_A),
    )
    assert edit_blocked.status_code == 403

    todays = client.get("/api/disposables/today", headers=auth_header(ADMIN)).json()
    assert todays == []  # collection date is in the future, not today


def test_calendar_event_create_and_list(client):
    register(client, ADMIN, "admin@example.com")
    _approve_user(client, USER_A, "a@example.com")
    committees = client.get("/api/committees", headers=auth_header(ADMIN)).json()

    create = client.post(
        "/api/calendar",
        json={"title": "Orientation", "date": "2026-11-15", "committee_id": committees[0]["id"]},
        headers=auth_header(ADMIN),
    )
    assert create.status_code == 201
    assert create.json()["committee_name"] == committees[0]["name"]

    # Non-admin without a committee_id in the body defaults to their own committee.
    create_user = client.post(
        "/api/calendar",
        json={"title": "Committee Meetup", "date": "2026-11-16"},
        headers=auth_header(USER_A),
    )
    assert create_user.status_code == 201

    events = client.get(
        "/api/calendar?start=2026-11-01&end=2026-11-30", headers=auth_header(USER_A)
    ).json()
    assert len(events) == 2

    # Admin needs an explicit committee_id since they belong to none.
    missing_committee = client.post(
        "/api/calendar", json={"title": "No committee", "date": "2026-11-17"}, headers=auth_header(ADMIN)
    )
    assert missing_committee.status_code == 400


def test_calendar_ics_feed(client):
    register(client, ADMIN, "admin@example.com")
    committees = client.get("/api/committees", headers=auth_header(ADMIN)).json()
    client.post(
        "/api/calendar",
        json={"title": "Orientation", "date": "2026-11-15", "committee_id": committees[0]["id"]},
        headers=auth_header(ADMIN),
    )

    resp = client.get("/api/calendar/feed.ics")
    assert resp.status_code == 200
    assert "BEGIN:VCALENDAR" in resp.text
    assert "Orientation" in resp.text

    feed_url = client.get("/api/calendar/feed-url", headers=auth_header(ADMIN)).json()["url"]
    assert feed_url.endswith("/api/calendar/feed.ics")
