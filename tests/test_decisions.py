"""Tests for the Decision model, API, and UI."""

import pytest


# ── Decision API ──────────────────────────────────────────────────────────────

def test_create_decision_valid(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    resp = client.post(
        f"/programs/{prog['id']}/decisions",
        json={"title": "Use PostgreSQL", "status": "proposed", "decision_date": "2026-06-01"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "Use PostgreSQL"
    assert body["status"] == "proposed"
    assert body["decision_date"] == "2026-06-01"
    assert body["display_id"].startswith("DEC-")
    assert body["program_id"] == prog["id"]


def test_create_decision_invalid_status(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    resp = client.post(
        f"/programs/{prog['id']}/decisions",
        json={"title": "D", "status": "not_a_status"},
    )
    assert resp.status_code == 422


def test_create_decision_program_not_found(client) -> None:
    resp = client.post("/programs/99999/decisions", json={"title": "D"})
    assert resp.status_code == 404


def test_list_decisions(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    client.post(f"/programs/{prog['id']}/decisions", json={"title": "D1"})
    client.post(f"/programs/{prog['id']}/decisions", json={"title": "D2"})
    resp = client.get(f"/programs/{prog['id']}/decisions")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_list_decisions_program_not_found(client) -> None:
    resp = client.get("/programs/99999/decisions")
    assert resp.status_code == 404


def test_get_decision(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    dec = client.post(f"/programs/{prog['id']}/decisions", json={"title": "D"}).json()
    resp = client.get(f"/decisions/{dec['id']}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "D"


def test_get_decision_not_found(client) -> None:
    assert client.get("/decisions/99999").status_code == 404


def test_update_decision(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    dec = client.post(f"/programs/{prog['id']}/decisions", json={"title": "D", "status": "proposed"}).json()
    resp = client.patch(f"/decisions/{dec['id']}", json={"status": "decided", "title": "D Final"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "decided"
    assert resp.json()["title"] == "D Final"


def test_delete_decision(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    dec = client.post(f"/programs/{prog['id']}/decisions", json={"title": "D"}).json()
    assert client.delete(f"/decisions/{dec['id']}").status_code == 204
    assert client.get(f"/decisions/{dec['id']}").status_code == 404


def test_delete_decision_not_found(client) -> None:
    assert client.delete("/decisions/99999").status_code == 404


def test_decision_display_ids_are_unique(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    d1 = client.post(f"/programs/{prog['id']}/decisions", json={"title": "D1"}).json()
    d2 = client.post(f"/programs/{prog['id']}/decisions", json={"title": "D2"}).json()
    assert d1["display_id"] != d2["display_id"]
    assert d1["display_id"].startswith("DEC-")
    assert d2["display_id"].startswith("DEC-")


def test_decision_all_statuses_valid(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    for s in ("proposed", "decided", "deferred", "superseded", "cancelled"):
        resp = client.post(f"/programs/{prog['id']}/decisions", json={"title": s, "status": s})
        assert resp.status_code == 201, f"status {s!r} should be valid"
        assert resp.json()["status"] == s


def test_decision_with_all_fields(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    resp = client.post(f"/programs/{prog['id']}/decisions", json={
        "title": "Full Decision",
        "description": "We decided this",
        "decision_date": "2026-07-15",
        "status": "decided",
        "owner": "Alice",
        "rationale": "Because it is better",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["owner"] == "Alice"
    assert body["rationale"] == "Because it is better"
    assert body["description"] == "We decided this"


# ── Decision UI ───────────────────────────────────────────────────────────────

def test_program_detail_shows_decisions_section(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    resp = client.get(f"/programs/{prog['id']}/view")
    assert resp.status_code == 200
    assert "Decisions" in resp.text
    assert "new-decision" in resp.text


def test_program_detail_shows_decision_row(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    client.post(
        f"/programs/{prog['id']}/decisions",
        json={"title": "Go Serverless", "status": "decided", "decision_date": "2026-06-10", "owner": "Bob"},
    )
    resp = client.get(f"/programs/{prog['id']}/view")
    assert resp.status_code == 200
    assert "Go Serverless" in resp.text
    assert "Decided" in resp.text
    assert "2026-06-10" in resp.text
    assert "Bob" in resp.text


def test_create_decision_via_ui(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    resp = client.post(
        f"/programs/{prog['id']}/decisions/create",
        data={"title": "Use Redis", "status": "proposed", "decision_date": "2026-09-01"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == f"/programs/{prog['id']}/view"
    decisions = client.get(f"/programs/{prog['id']}/decisions").json()
    assert len(decisions) == 1
    assert decisions[0]["title"] == "Use Redis"


def test_create_decision_via_ui_missing_title(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    resp = client.post(
        f"/programs/{prog['id']}/decisions/create",
        data={"title": "", "status": "proposed"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "show_new_decision=1" in resp.headers["location"]


def test_decide_decision_via_ui(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    dec = client.post(
        f"/programs/{prog['id']}/decisions",
        json={"title": "D", "status": "proposed"},
    ).json()
    resp = client.post(f"/decisions/{dec['id']}/decide-ui", follow_redirects=False)
    assert resp.status_code == 303
    assert client.get(f"/decisions/{dec['id']}").json()["status"] == "decided"


def test_delete_decision_via_ui(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    dec = client.post(f"/programs/{prog['id']}/decisions", json={"title": "D"}).json()
    resp = client.post(f"/decisions/{dec['id']}/delete", follow_redirects=False)
    assert resp.status_code == 303
    assert client.get(f"/decisions/{dec['id']}").status_code == 404


def test_edit_decision_panel_opens_inline(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    dec = client.post(f"/programs/{prog['id']}/decisions", json={"title": "Inline Dec"}).json()
    resp = client.get(f"/programs/{prog['id']}/view?edit_decision_id={dec['id']}")
    assert resp.status_code == 200
    assert '<details id="edit-decision" class="collapsible-panel" open>' in resp.text
    assert "Inline Dec" in resp.text


# ── Decision + Relationship integration ──────────────────────────────────────

def test_create_relationship_with_decision(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    dec = client.post(f"/programs/{prog['id']}/decisions", json={"title": "D"}).json()
    risk = client.post(
        f"/programs/{prog['id']}/risks",
        json={"title": "R", "severity": "high", "likelihood": "likely"},
    ).json()
    resp = client.post("/relationships", json={
        "source_type": "decision",
        "source_id": dec["id"],
        "relationship_type": "mitigates",
        "target_type": "risk",
        "target_id": risk["id"],
    })
    assert resp.status_code == 201
    assert resp.json()["source_type"] == "decision"
    assert resp.json()["display_id"].startswith("REL-")


def test_decision_appears_in_relationship_picker(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    dec = client.post(f"/programs/{prog['id']}/decisions", json={"title": "My Decision"}).json()
    resp = client.get(f"/programs/{prog['id']}/view")
    assert resp.status_code == 200
    assert dec["display_id"] in resp.text
    assert "My Decision" in resp.text


def test_decision_relationship_shown_on_detail_page(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    dec = client.post(f"/programs/{prog['id']}/decisions", json={"title": "Decision"}).json()
    ms = client.post(f"/programs/{prog['id']}/milestones", json={"title": "MS"}).json()
    client.post("/relationships", json={
        "source_type": "decision", "source_id": dec["id"],
        "relationship_type": "tracks", "target_type": "milestone", "target_id": ms["id"],
    })
    resp = client.get(f"/programs/{prog['id']}/view")
    assert resp.status_code == 200
    assert dec["display_id"] in resp.text
    assert "tracks" in resp.text


def test_program_relationships_includes_decision_relationships(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    dec = client.post(f"/programs/{prog['id']}/decisions", json={"title": "D"}).json()
    wi = client.post(
        f"/programs/{prog['id']}/work-items",
        json={"title": "WI", "status": "open", "priority": "medium"},
    ).json()
    client.post("/relationships", json={
        "source_type": "decision", "source_id": dec["id"],
        "relationship_type": "relates_to", "target_type": "work_item", "target_id": wi["id"],
    })
    rels = client.get(f"/programs/{prog['id']}/relationships").json()
    assert len(rels) == 1
    assert rels[0]["source_type"] == "decision"
