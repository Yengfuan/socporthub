from tests.conftest import auth_header

ADMIN = 999
USER_A = 1001


def _register_and_approve(client, telegram_id, email):
    client.post(
        "/api/auth/register",
        json={"email": email, "display_name": "User A"},
        headers=auth_header(telegram_id),
    )
    users = client.get("/api/admin/users", headers=auth_header(ADMIN)).json()
    user_id = next(u["id"] for u in users if u["telegram_id"] == telegram_id)
    committees = client.get("/api/committees", headers=auth_header(ADMIN)).json()
    client.patch(
        f"/api/admin/users/{user_id}",
        json={"status": "approved", "committee_ids": [committees[0]["id"]]},
        headers=auth_header(ADMIN),
    )


def test_email_draft_edit_and_send_advances_proposal(client, monkeypatch):
    client.post("/api/auth/register", json={"email": "admin@example.com"}, headers=auth_header(ADMIN))
    _register_and_approve(client, USER_A, "a@example.com")
    proposal = client.post("/api/proposals", json={"title": "Movie Night"}, headers=auth_header(USER_A)).json()
    client.patch(f"/api/proposals/{proposal['id']}", json={"status": "in_review"}, headers=auth_header(ADMIN))

    draft = client.get(f"/api/email/preview/{proposal['id']}", headers=auth_header(ADMIN))
    assert draft.status_code == 200
    assert "Movie Night" in draft.json()["subject"]
    assert "Supporting document" not in draft.json()["body"]
    edited = client.patch(
        f"/api/email/preview/{proposal['id']}",
        json={"subject": "Updated subject", "body": "Updated body https://example.com"},
        headers=auth_header(ADMIN),
    )
    assert "https://" in edited.json()["body"]

    async def fake_send_email(**kwargs):
        assert kwargs["to"] == "a@example.com"
        assert "http" not in kwargs["subject"]
        assert "http" not in kwargs["body"]

    monkeypatch.setattr("api.routes.email.send_email", fake_send_email)
    sent = client.post(f"/api/email/send/{proposal['id']}", headers=auth_header(ADMIN))
    assert sent.status_code == 200
    assert client.get(f"/api/proposals/{proposal['id']}", headers=auth_header(ADMIN)).json()["status"] == "submitted"


def test_reminder_inbox_and_read_state(client):
    client.post("/api/auth/register", json={"email": "admin@example.com"}, headers=auth_header(ADMIN))
    _register_and_approve(client, USER_A, "a@example.com")
    reminder = client.post(
        "/api/reminders", json={"message": "Please review this"}, headers=auth_header(USER_A)
    )
    assert reminder.status_code == 201
    reminder_id = reminder.json()["id"]
    assert client.get("/api/reminders/unread-count", headers=auth_header(ADMIN)).json() == {"count": 1}
    assert client.patch(f"/api/reminders/{reminder_id}/read", json={}, headers=auth_header(ADMIN)).status_code == 200
    assert client.get("/api/reminders/unread-count", headers=auth_header(ADMIN)).json() == {"count": 0}
