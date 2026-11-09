from tests.conftest import auth_header
from tests.test_phase3 import ADMIN, USER_A, _approve_user, register

USER_B = 1002
BLOCKOUT_DATE = "2030-03-27"


def _setup(client):
    register(client, ADMIN, "admin@example.com")
    _approve_user(client, USER_A, "a@example.com", committee_index=0)  # Block 2
    _approve_user(client, USER_B, "b@example.com", committee_index=1)  # Soccom
    committees = client.get("/api/committees", headers=auth_header(ADMIN)).json()
    return committees[0]["id"], committees[1]["id"]


def _add_blockout(client, committee_id, date=BLOCKOUT_DATE):
    return client.post(
        "/api/calendar",
        json={"title": "Night Cycling", "event_date": date, "committee_id": committee_id, "is_blockout": True},
        headers=auth_header(ADMIN),
    )


def _proposal(client, telegram_id, date=BLOCKOUT_DATE):
    resp = client.post(
        "/api/proposals",
        json={"title": "Movie Night", "event_date": date, "save_draft": True},
        headers=auth_header(telegram_id),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_only_admin_can_create_blockout(client):
    block2, _soccom = _setup(client)
    resp = client.post(
        "/api/calendar",
        json={"title": "Sneaky", "event_date": BLOCKOUT_DATE, "is_blockout": True},
        headers=auth_header(USER_A),
    )
    assert resp.status_code == 403
    assert _add_blockout(client, block2).json()["is_blockout"] is True


def test_blockout_list_visible_to_all_ccas_and_hides_normal_events(client):
    block2, soccom = _setup(client)
    _add_blockout(client, soccom)
    client.post(
        "/api/calendar",
        json={"title": "Normal", "event_date": BLOCKOUT_DATE, "committee_id": block2},
        headers=auth_header(ADMIN),
    )
    listed = client.get("/api/calendar/blockouts", headers=auth_header(USER_A)).json()
    assert [b["title"] for b in listed] == ["Night Cycling"]
    assert listed[0]["committee_id"] == soccom


def test_proposal_clash_warns_other_ccas_but_not_the_owner(client):
    _block2, soccom = _setup(client)
    _add_blockout(client, soccom)

    other = _proposal(client, USER_A)  # Block 2 proposal on Soccom's block-out date
    owner = _proposal(client, USER_B)  # Soccom's own proposal
    clash = client.get(f"/api/proposals/{other}", headers=auth_header(USER_A)).json()["blockout_clash"]
    assert "Soccom" in clash and "Night Cycling" in clash
    assert client.get(f"/api/proposals/{owner}", headers=auth_header(USER_B)).json()["blockout_clash"] is None

    listed = client.get("/api/proposals", headers=auth_header(USER_A)).json()
    assert listed[0]["blockout_clash"] == clash


def test_clash_appears_when_blockout_added_later_and_clears_when_removed(client):
    _block2, soccom = _setup(client)
    proposal_id = _proposal(client, USER_A)
    url = f"/api/proposals/{proposal_id}"
    assert client.get(url, headers=auth_header(USER_A)).json()["blockout_clash"] is None

    blockout_id = _add_blockout(client, soccom).json()["id"]
    assert client.get(url, headers=auth_header(USER_A)).json()["blockout_clash"] is not None

    client.delete(f"/api/calendar/{blockout_id}", headers=auth_header(ADMIN))
    assert client.get(url, headers=auth_header(USER_A)).json()["blockout_clash"] is None


def test_ics_feed_marks_blockouts(client):
    _block2, soccom = _setup(client)
    _add_blockout(client, soccom)
    assert "BLOCKED: Night Cycling" in client.get("/api/calendar/feed.ics").text
