from tests.conftest import auth_header
from tests.test_phase3 import ADMIN, USER_A, _approve_user, register

MATE = 1003  # same committee as USER_A
OUTSIDER = 1002  # a different committee


def _setup(client):
    register(client, ADMIN, "admin@example.com")
    _approve_user(client, USER_A, "a@example.com", committee_index=0)
    _approve_user(client, MATE, "mate@example.com", committee_index=0)
    _approve_user(client, OUTSIDER, "out@example.com", committee_index=1)


def _needs_action_proposal(client):
    """USER_A's proposal, submitted, then sent back by the admin."""
    resp = client.post(
        "/api/proposals",
        json={"title": "Movie Night", "category": "pubs", "event_date": "2030-05-01", "save_draft": True},
        headers=auth_header(USER_A),
    )
    assert resp.status_code == 201, resp.text
    pid = resp.json()["id"]
    sub = client.patch(f"/api/proposals/{pid}", json={"status": "in_review"}, headers=auth_header(USER_A))
    assert sub.status_code == 200, sub.text
    back = client.patch(f"/api/proposals/{pid}", json={"status": "needs_action"}, headers=auth_header(ADMIN))
    assert back.status_code == 200, back.text
    return pid


def test_committee_mate_can_edit_and_resubmit(client):
    _setup(client)
    pid = _needs_action_proposal(client)

    edit = client.patch(f"/api/proposals/{pid}", json={"title": "Movie Night v2"}, headers=auth_header(MATE))
    assert edit.status_code == 200 and edit.json()["title"] == "Movie Night v2"
    resubmit = client.patch(f"/api/proposals/{pid}", json={"status": "in_review"}, headers=auth_header(MATE))
    assert resubmit.status_code == 200 and resubmit.json()["status"] == "in_review"
    # The history still records who made the change.
    history = client.get(f"/api/proposals/{pid}/status-history", headers=auth_header(ADMIN)).json()
    last = history[-1]
    assert last["to_status"] == "in_review"
    assert last["changed_by"] != history[0]["changed_by"]  # the mate, not the original submitter


def test_other_committee_cannot_edit_or_resubmit(client):
    _setup(client)
    pid = _needs_action_proposal(client)
    # A different committee can't even see the proposal.
    assert client.patch(f"/api/proposals/{pid}", json={"title": "Hacked"}, headers=auth_header(OUTSIDER)).status_code == 404
    assert client.patch(f"/api/proposals/{pid}", json={"status": "in_review"}, headers=auth_header(OUTSIDER)).status_code == 404


def test_committee_mate_cannot_edit_outside_editable_statuses(client):
    _setup(client)
    pid = _needs_action_proposal(client)
    client.patch(f"/api/proposals/{pid}", json={"status": "in_review"}, headers=auth_header(USER_A))
    resp = client.patch(f"/api/proposals/{pid}", json={"title": "Sneaky"}, headers=auth_header(MATE))
    assert resp.status_code == 403


def test_committee_mate_can_upload_poster(client):
    _setup(client)
    resp = client.post(
        "/api/proposals",
        json={"title": "Movie Night", "category": "merch", "event_date": "2030-05-01", "save_draft": True},
        headers=auth_header(USER_A),
    )
    pid = resp.json()["id"]
    up = client.post(
        f"/api/proposals/{pid}/poster",
        files={"poster": ("p.png", b"\x89PNG", "image/png")},
        headers=auth_header(MATE),
    )
    assert up.status_code == 200, up.text


def test_committee_mate_can_request_deletion_and_see_it(client):
    _setup(client)
    pid = _needs_action_proposal(client)
    created = client.post(
        "/api/proposal-deletions", json={"proposal_id": pid, "reason": "Cancelled"}, headers=auth_header(MATE)
    )
    assert created.status_code == 201
    # The original submitter sees the pending request too; an outsider sees nothing.
    seen = client.get(f"/api/proposal-deletions?proposal_id={pid}", headers=auth_header(USER_A)).json()
    assert [r["status"] for r in seen] == ["pending"]
    assert client.get("/api/proposal-deletions", headers=auth_header(OUTSIDER)).json() == []
    assert client.post(
        "/api/proposal-deletions", json={"proposal_id": pid, "reason": "x"}, headers=auth_header(OUTSIDER)
    ).status_code == 404


def test_committee_mate_gets_unread_admin_comment(client):
    _setup(client)
    pid = _needs_action_proposal(client)
    client.post(f"/api/proposals/{pid}/comments", json={"body": "Fix the date"}, headers=auth_header(ADMIN))
    for telegram_id in (USER_A, MATE):
        listed = client.get("/api/proposals", headers=auth_header(telegram_id)).json()
        assert listed[0]["unread_comment_count"] >= 1
    assert client.get("/api/proposals", headers=auth_header(OUTSIDER)).json() == []
