from api.models import (
    CalendarEvent,
    DeletionRequestStatus,
    DisposableRequest,
    EmailDraft,
    Proposal,
    ProposalComment,
    ProposalDeletionRequest,
    ProposalStatusHistory,
)
from api.database import get_db
from api.main import app
from tests.conftest import auth_header
from tests.test_phase3 import ADMIN, USER_A, _approve_user, register

USER_B = 1002


def _setup(client):
    register(client, ADMIN, "admin@example.com")
    _approve_user(client, USER_A, "a@example.com", committee_index=0)
    _approve_user(client, USER_B, "b@example.com", committee_index=1)


def _proposal(client, telegram_id=USER_A, date="2030-05-01"):
    resp = client.post(
        "/api/proposals",
        json={"title": "Movie Night", "event_date": date, "save_draft": True},
        headers=auth_header(telegram_id),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _db():
    return next(app.dependency_overrides[get_db]())


def _count(model, **filters):
    db = _db()
    try:
        return db.query(model).filter_by(**filters).count()
    finally:
        db.close()


def _attach_related_rows(client, proposal_id):
    """Comment, status history, a calendar entry and a disposable request on the proposal."""
    client.post(
        f"/api/proposals/{proposal_id}/comments", json={"body": "hello"}, headers=auth_header(USER_A)
    )
    db = _db()
    try:
        proposal = db.get(Proposal, proposal_id)
        from datetime import date

        db.add(
            CalendarEvent(
                committee_id=proposal.committee_id,
                created_by=proposal.submitted_by,
                proposal_id=proposal_id,
                title=proposal.title,
                event_date=date(2030, 5, 1),
            )
        )
        db.add(
            DisposableRequest(
                proposal_id=proposal_id,
                committee_id=proposal.committee_id,
                requester_cca="Block 2",
                requested_by=proposal.submitted_by,
                activity_name="Movie Night",
                collection_date=date(2030, 5, 1),
            )
        )
        db.add(EmailDraft(proposal_id=proposal_id, recipient="x@example.com", subject="s", body="b"))
        db.add(ProposalStatusHistory(proposal_id=proposal_id, changed_by=proposal.submitted_by, to_status=proposal.status))
        db.commit()
    finally:
        db.close()


def test_admin_deletes_proposal_and_all_related_rows(client):
    _setup(client)
    pid = _proposal(client)
    _attach_related_rows(client, pid)

    resp = client.delete(f"/api/proposals/{pid}", headers=auth_header(ADMIN))
    assert resp.status_code == 204
    assert _count(Proposal, id=pid) == 0
    for model in (ProposalComment, ProposalStatusHistory, DisposableRequest, EmailDraft, CalendarEvent):
        assert _count(model, proposal_id=pid) == 0, model.__name__
    assert client.get(f"/api/proposals/{pid}", headers=auth_header(ADMIN)).status_code == 404


def test_user_cannot_delete_directly(client):
    _setup(client)
    pid = _proposal(client)
    assert client.delete(f"/api/proposals/{pid}", headers=auth_header(USER_A)).status_code == 403
    assert _count(Proposal, id=pid) == 1


def test_calendar_entry_of_other_proposal_survives(client):
    _setup(client)
    first, second = _proposal(client), _proposal(client)
    _attach_related_rows(client, first)
    _attach_related_rows(client, second)
    client.delete(f"/api/proposals/{first}", headers=auth_header(ADMIN))
    assert _count(CalendarEvent, proposal_id=second) == 1


def test_user_request_then_admin_approves(client):
    _setup(client)
    pid = _proposal(client)
    _attach_related_rows(client, pid)

    created = client.post(
        "/api/proposal-deletions", json={"proposal_id": pid, "reason": "Event cancelled"}, headers=auth_header(USER_A)
    )
    assert created.status_code == 201
    request_id = created.json()["id"]
    # Still there while pending; admin sees it, and a second request is refused.
    assert _count(Proposal, id=pid) == 1
    pending = client.get("/api/proposal-deletions", headers=auth_header(ADMIN)).json()
    assert [r["id"] for r in pending] == [request_id]
    assert client.post(
        "/api/proposal-deletions", json={"proposal_id": pid, "reason": "again"}, headers=auth_header(USER_A)
    ).status_code == 409

    approved = client.post(f"/api/proposal-deletions/{request_id}/approve", headers=auth_header(ADMIN))
    assert approved.status_code == 200 and approved.json()["status"] == "approved"
    assert _count(Proposal, id=pid) == 0
    assert _count(CalendarEvent, proposal_id=pid) == 0
    # The request (and its reason) outlives the proposal, and shows in the user's list.
    mine = client.get("/api/proposal-deletions", headers=auth_header(USER_A)).json()
    assert mine[0]["reason"] == "Event cancelled" and mine[0]["proposal_title"] == "Movie Night"
    assert client.get("/api/proposal-deletions", headers=auth_header(ADMIN)).json() == []


def test_rejection_keeps_proposal_and_allows_new_request(client):
    _setup(client)
    pid = _proposal(client)
    request_id = client.post(
        "/api/proposal-deletions", json={"proposal_id": pid, "reason": "oops"}, headers=auth_header(USER_A)
    ).json()["id"]
    rejected = client.post(
        f"/api/proposal-deletions/{request_id}/reject", json={"note": "Please keep it"}, headers=auth_header(ADMIN)
    )
    assert rejected.json()["status"] == "rejected" and rejected.json()["decision_note"] == "Please keep it"
    assert _count(Proposal, id=pid) == 1
    assert client.post(
        f"/api/proposal-deletions/{request_id}/approve", headers=auth_header(ADMIN)
    ).status_code == 409
    assert client.post(
        "/api/proposal-deletions", json={"proposal_id": pid, "reason": "really"}, headers=auth_header(USER_A)
    ).status_code == 201


def test_request_permissions_and_validation(client):
    _setup(client)
    pid = _proposal(client)
    # Not the submitter, admin, empty reason.
    assert client.post(
        "/api/proposal-deletions", json={"proposal_id": pid, "reason": "x"}, headers=auth_header(USER_B)
    ).status_code == 404
    assert client.post(
        "/api/proposal-deletions", json={"proposal_id": pid, "reason": "x"}, headers=auth_header(ADMIN)
    ).status_code == 400
    assert client.post(
        "/api/proposal-deletions", json={"proposal_id": pid, "reason": "   "}, headers=auth_header(USER_A)
    ).status_code == 400
    request_id = client.post(
        "/api/proposal-deletions", json={"proposal_id": pid, "reason": "x"}, headers=auth_header(USER_A)
    ).json()["id"]
    # Users can't decide their own request.
    assert client.post(f"/api/proposal-deletions/{request_id}/approve", headers=auth_header(USER_A)).status_code == 403
    assert _count(Proposal, id=pid) == 1


def test_direct_admin_delete_closes_pending_request(client):
    _setup(client)
    pid = _proposal(client)
    client.post("/api/proposal-deletions", json={"proposal_id": pid, "reason": "x"}, headers=auth_header(USER_A))
    client.delete(f"/api/proposals/{pid}", headers=auth_header(ADMIN))
    assert _count(ProposalDeletionRequest, proposal_id=pid, status=DeletionRequestStatus.approved) == 1


def test_finished_proposal_calendar_entry_is_linked(client):
    _setup(client)
    pid = _proposal(client)
    db = _db()
    try:
        from api.models import ProposalStatus

        db.get(Proposal, pid).status = ProposalStatus.submitted
        db.commit()
    finally:
        db.close()
    resp = client.patch(f"/api/proposals/{pid}", json={"status": "finished"}, headers=auth_header(ADMIN))
    assert resp.status_code == 200, resp.text
    assert _count(CalendarEvent, proposal_id=pid) == 1
