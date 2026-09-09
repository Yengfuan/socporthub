from tests.conftest import auth_header


ADMIN = 999
USER_A = 1001


def test_admin_can_edit_user_email_and_existing_draft_recipient(client):
    client.post("/api/auth/register", json={"email": "admin@example.com"}, headers=auth_header(ADMIN))
    registered = client.post(
        "/api/auth/register",
        json={"email": "old@example.com", "display_name": "User A"},
        headers=auth_header(USER_A),
    )
    user_id = registered.json()["id"]
    committees = client.get("/api/committees", headers=auth_header(ADMIN)).json()
    client.patch(
        f"/api/admin/users/{user_id}",
        json={"status": "approved", "committee_ids": [committees[0]["id"]]},
        headers=auth_header(ADMIN),
    )

    proposal = client.post(
        "/api/proposals", json={"title": "Movie Night"}, headers=auth_header(USER_A)
    ).json()
    draft = client.get(f"/api/email/preview/{proposal['id']}", headers=auth_header(ADMIN))
    assert draft.json()["recipient"] == "old@example.com"

    updated = client.patch(
        f"/api/admin/users/{user_id}",
        json={"email": "new@example.com"},
        headers=auth_header(ADMIN),
    )
    assert updated.status_code == 200
    assert updated.json()["email"] == "new@example.com"

    draft = client.get(f"/api/email/preview/{proposal['id']}", headers=auth_header(ADMIN))
    assert draft.json()["recipient"] == "new@example.com"


def test_user_cannot_edit_email_and_duplicate_is_rejected(client):
    client.post("/api/auth/register", json={"email": "admin@example.com"}, headers=auth_header(ADMIN))
    user = client.post(
        "/api/auth/register", json={"email": "user@example.com"}, headers=auth_header(USER_A)
    ).json()

    forbidden = client.patch(
        f"/api/admin/users/{user['id']}",
        json={"email": "changed@example.com"},
        headers=auth_header(USER_A),
    )
    assert forbidden.status_code == 403

    duplicate = client.patch(
        f"/api/admin/users/{user['id']}",
        json={"email": "admin@example.com"},
        headers=auth_header(ADMIN),
    )
    assert duplicate.status_code == 409
