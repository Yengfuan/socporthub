from tests.conftest import auth_header

ADMIN = 999
USER_A = 1001
USER_B = 1002


def register(client, telegram_id, email):
    return client.post(
        "/api/auth/register",
        json={"email": email, "display_name": email.split("@")[0]},
        headers=auth_header(telegram_id),
    )


def test_admin_auto_approved_on_registration(client):
    resp = register(client, ADMIN, "admin@example.com")
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"
    assert resp.json()["status"] == "approved"


def test_regular_user_starts_pending_and_is_blocked_until_approved(client):
    register(client, ADMIN, "admin@example.com")
    register(client, USER_A, "a@example.com")

    resp = client.get("/api/proposals", headers=auth_header(USER_A))
    assert resp.status_code == 403  # not approved yet

    users = client.get("/api/admin/users", headers=auth_header(ADMIN)).json()
    user_a_id = next(u["id"] for u in users if u["telegram_id"] == USER_A)
    committees = client.get("/api/committees", headers=auth_header(ADMIN)).json()

    approve = client.patch(
        f"/api/admin/users/{user_a_id}",
        json={"status": "approved", "committee_ids": [committees[0]["id"]]},
        headers=auth_header(ADMIN),
    )
    assert approve.status_code == 200
    assert approve.json()["status"] == "approved"

    resp = client.get("/api/proposals", headers=auth_header(USER_A))
    assert resp.status_code == 200
    assert resp.json() == []


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


def test_proposal_lifecycle_and_status_guardrails(client):
    register(client, ADMIN, "admin@example.com")
    _approve_user(client, USER_A, "a@example.com")

    create = client.post(
        "/api/proposals",
        json={"title": "Movie Night", "description": "Fun", "event_date": "2026-10-01"},
        headers=auth_header(USER_A),
    )
    assert create.status_code == 201
    proposal_id = create.json()["id"]
    assert create.json()["status"] == "needs_action"

    # Illegal skip-ahead transition rejected.
    bad = client.patch(
        f"/api/proposals/{proposal_id}",
        json={"status": "finished"},
        headers=auth_header(ADMIN),
    )
    assert bad.status_code == 400

    # Non-admin can't change status.
    forbidden = client.patch(
        f"/api/proposals/{proposal_id}",
        json={"status": "in_review"},
        headers=auth_header(USER_A),
    )
    assert forbidden.status_code == 403

    # Legal transition by admin.
    ok = client.patch(
        f"/api/proposals/{proposal_id}",
        json={"status": "in_review"},
        headers=auth_header(ADMIN),
    )
    assert ok.status_code == 200
    assert ok.json()["status"] == "in_review"

    # Owner can no longer edit content once out of needs_action.
    edit_blocked = client.patch(
        f"/api/proposals/{proposal_id}",
        json={"title": "Hacked"},
        headers=auth_header(USER_A),
    )
    assert edit_blocked.status_code == 403


def test_admin_can_clear_event_date_after_finished(client):
    register(client, ADMIN, "admin@example.com")
    _approve_user(client, USER_A, "a@example.com")

    create = client.post(
        "/api/proposals",
        json={"title": "Movie Night", "event_date": "2026-10-01"},
        headers=auth_header(USER_A),
    )
    proposal_id = create.json()["id"]

    client.patch(f"/api/proposals/{proposal_id}", json={"status": "in_review"}, headers=auth_header(ADMIN))
    client.patch(f"/api/proposals/{proposal_id}", json={"status": "submitted"}, headers=auth_header(ADMIN))
    finish = client.patch(f"/api/proposals/{proposal_id}", json={"status": "finished"}, headers=auth_header(ADMIN))
    assert finish.json()["event_date"] == "2026-10-01"

    # Omitting event_date entirely leaves it untouched.
    untouched = client.patch(f"/api/proposals/{proposal_id}", json={"description": "note"}, headers=auth_header(ADMIN))
    assert untouched.json()["event_date"] == "2026-10-01"

    # Admin can edit content fields even after finished, and explicit null clears it.
    cleared = client.patch(f"/api/proposals/{proposal_id}", json={"event_date": None}, headers=auth_header(ADMIN))
    assert cleared.status_code == 200
    assert cleared.json()["event_date"] is None

    # title is NOT NULL at the DB level — clearing it is rejected, not a 500.
    title_clear = client.patch(f"/api/proposals/{proposal_id}", json={"title": None}, headers=auth_header(ADMIN))
    assert title_clear.status_code == 400


def test_committee_scoped_visibility(client):
    register(client, ADMIN, "admin@example.com")
    _approve_user(client, USER_A, "a@example.com", committee_index=0)
    _approve_user(client, USER_B, "b@example.com", committee_index=1)

    client.post(
        "/api/proposals",
        json={"title": "Block 2 Event"},
        headers=auth_header(USER_A),
    )

    # User B is in a different committee and shouldn't see A's proposal.
    visible_to_b = client.get("/api/proposals", headers=auth_header(USER_B)).json()
    assert visible_to_b == []

    # Admin sees everything.
    visible_to_admin = client.get("/api/proposals", headers=auth_header(ADMIN)).json()
    assert len(visible_to_admin) == 1
