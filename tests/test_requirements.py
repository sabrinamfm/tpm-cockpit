"""Tests for the Requirement model, API, UI, filters, and relationship integration."""

import pytest


# ── Requirement API ───────────────────────────────────────────────────────────

def test_create_requirement_valid(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    resp = client.post(
        f"/programs/{prog['id']}/requirements",
        json={"title": "GDPR Compliance", "source_type": "compliance", "status": "proposed"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "GDPR Compliance"
    assert body["source_type"] == "compliance"
    assert body["status"] == "proposed"
    assert body["display_id"].startswith("REQ-")
    assert body["program_id"] == prog["id"]


def test_create_requirement_invalid_source_type(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    resp = client.post(
        f"/programs/{prog['id']}/requirements",
        json={"title": "R", "source_type": "not_a_type"},
    )
    assert resp.status_code == 422


def test_create_requirement_invalid_status(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    resp = client.post(
        f"/programs/{prog['id']}/requirements",
        json={"title": "R", "status": "not_a_status"},
    )
    assert resp.status_code == 422


def test_create_requirement_program_not_found(client) -> None:
    resp = client.post("/programs/99999/requirements", json={"title": "R"})
    assert resp.status_code == 404


def test_list_requirements(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    client.post(f"/programs/{prog['id']}/requirements", json={"title": "R1"})
    client.post(f"/programs/{prog['id']}/requirements", json={"title": "R2"})
    resp = client.get(f"/programs/{prog['id']}/requirements")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_list_requirements_program_not_found(client) -> None:
    resp = client.get("/programs/99999/requirements")
    assert resp.status_code == 404


def test_get_requirement(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    req = client.post(f"/programs/{prog['id']}/requirements", json={"title": "R"}).json()
    resp = client.get(f"/requirements/{req['id']}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "R"


def test_get_requirement_not_found(client) -> None:
    assert client.get("/requirements/99999").status_code == 404


def test_update_requirement(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    req = client.post(
        f"/programs/{prog['id']}/requirements",
        json={"title": "R", "status": "proposed"},
    ).json()
    resp = client.patch(f"/requirements/{req['id']}", json={"status": "accepted", "title": "R Updated"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"
    assert resp.json()["title"] == "R Updated"


def test_delete_requirement(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    req = client.post(f"/programs/{prog['id']}/requirements", json={"title": "R"}).json()
    assert client.delete(f"/requirements/{req['id']}").status_code == 204
    assert client.get(f"/requirements/{req['id']}").status_code == 404


def test_delete_requirement_not_found(client) -> None:
    assert client.delete("/requirements/99999").status_code == 404


def test_requirement_display_ids_are_unique(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    r1 = client.post(f"/programs/{prog['id']}/requirements", json={"title": "R1"}).json()
    r2 = client.post(f"/programs/{prog['id']}/requirements", json={"title": "R2"}).json()
    assert r1["display_id"] != r2["display_id"]
    assert r1["display_id"].startswith("REQ-")
    assert r2["display_id"].startswith("REQ-")


def test_requirement_all_source_types_valid(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    for st in (
        "okr", "change_management", "customer_commitment", "compliance",
        "leadership_request", "strategic_initiative", "operational_requirement", "other",
    ):
        resp = client.post(f"/programs/{prog['id']}/requirements", json={"title": st, "source_type": st})
        assert resp.status_code == 201, f"source_type {st!r} should be valid"
        assert resp.json()["source_type"] == st


def test_requirement_all_statuses_valid(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    for s in ("proposed", "accepted", "in_progress", "delivered", "deferred", "cancelled"):
        resp = client.post(f"/programs/{prog['id']}/requirements", json={"title": s, "status": s})
        assert resp.status_code == 201, f"status {s!r} should be valid"
        assert resp.json()["status"] == s


def test_requirement_with_all_fields(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    resp = client.post(f"/programs/{prog['id']}/requirements", json={
        "title": "Full Requirement",
        "description": "Full description",
        "source_type": "okr",
        "status": "accepted",
        "owner": "Alice",
        "target_date": "2026-09-01",
        "link": "https://example.com/req",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["owner"] == "Alice"
    assert body["target_date"] == "2026-09-01"
    assert body["link"] == "https://example.com/req"
    assert body["description"] == "Full description"


# ── Requirement UI ────────────────────────────────────────────────────────────

def test_program_detail_shows_requirements_section(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    resp = client.get(f"/programs/{prog['id']}/view")
    assert resp.status_code == 200
    assert "Requirements" in resp.text
    assert "new-requirement" in resp.text


def test_program_detail_shows_requirement_row(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    client.post(
        f"/programs/{prog['id']}/requirements",
        json={
            "title": "Q4 OKR", "source_type": "okr", "status": "accepted",
            "owner": "Bob", "target_date": "2026-12-01",
        },
    )
    resp = client.get(f"/programs/{prog['id']}/view")
    assert resp.status_code == 200
    assert "Q4 OKR" in resp.text
    assert "Accepted" in resp.text
    assert "2026-12-01" in resp.text
    assert "Bob" in resp.text


def test_program_detail_shows_requirement_link(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    client.post(
        f"/programs/{prog['id']}/requirements",
        json={"title": "Linked Req", "link": "https://example.com/req"},
    )
    resp = client.get(f"/programs/{prog['id']}/view")
    assert resp.status_code == 200
    assert "https://example.com/req" in resp.text


def test_create_requirement_via_ui(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    resp = client.post(
        f"/programs/{prog['id']}/requirements/create",
        data={"title": "OKR Req", "source_type": "okr", "status": "proposed"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == f"/programs/{prog['id']}/view"
    reqs = client.get(f"/programs/{prog['id']}/requirements").json()
    assert len(reqs) == 1
    assert reqs[0]["title"] == "OKR Req"


def test_create_requirement_via_ui_missing_title(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    resp = client.post(
        f"/programs/{prog['id']}/requirements/create",
        data={"title": "", "source_type": "okr", "status": "proposed"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "show_new_requirement=1" in resp.headers["location"]


def test_deliver_requirement_via_ui(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    req = client.post(
        f"/programs/{prog['id']}/requirements",
        json={"title": "R", "status": "in_progress"},
    ).json()
    resp = client.post(f"/requirements/{req['id']}/deliver-ui", follow_redirects=False)
    assert resp.status_code == 303
    assert client.get(f"/requirements/{req['id']}").json()["status"] == "delivered"


def test_delete_requirement_via_ui(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    req = client.post(f"/programs/{prog['id']}/requirements", json={"title": "R"}).json()
    resp = client.post(f"/requirements/{req['id']}/delete", follow_redirects=False)
    assert resp.status_code == 303
    assert client.get(f"/requirements/{req['id']}").status_code == 404


def test_edit_requirement_panel_opens_inline(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    req = client.post(f"/programs/{prog['id']}/requirements", json={"title": "Inline Req"}).json()
    resp = client.get(f"/programs/{prog['id']}/view?edit_requirement_id={req['id']}")
    assert resp.status_code == 200
    assert '<details id="edit-requirement" class="collapsible-panel" open>' in resp.text
    assert "Inline Req" in resp.text


# ── Requirement filters ───────────────────────────────────────────────────────

def test_requirement_filter_by_source_type(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    client.post(f"/programs/{prog['id']}/requirements", json={"title": "OKR req", "source_type": "okr"})
    client.post(f"/programs/{prog['id']}/requirements", json={"title": "Compliance req", "source_type": "compliance"})
    resp = client.get(f"/programs/{prog['id']}/view?req_source_type_filter=okr")
    assert resp.status_code == 200
    assert "OKR req" in resp.text
    assert "</span>Compliance req" not in resp.text


def test_requirement_filter_by_status(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    client.post(f"/programs/{prog['id']}/requirements", json={"title": "Proposed req", "status": "proposed"})
    client.post(f"/programs/{prog['id']}/requirements", json={"title": "Delivered req", "status": "delivered"})
    resp = client.get(f"/programs/{prog['id']}/view?req_status_filter=proposed")
    assert resp.status_code == 200
    assert "Proposed req" in resp.text
    assert "</span>Delivered req" not in resp.text


def test_requirement_filter_by_owner(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    client.post(f"/programs/{prog['id']}/requirements", json={"title": "Alice req", "owner": "Alice"})
    client.post(f"/programs/{prog['id']}/requirements", json={"title": "Bob req", "owner": "Bob"})
    resp = client.get(f"/programs/{prog['id']}/view?req_owner_filter=Alice")
    assert resp.status_code == 200
    assert "Alice req" in resp.text
    assert "</span>Bob req" not in resp.text


# ── Requirement + Relationship integration ────────────────────────────────────

def test_create_relationship_with_requirement(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    req = client.post(f"/programs/{prog['id']}/requirements", json={"title": "R"}).json()
    ms = client.post(f"/programs/{prog['id']}/milestones", json={"title": "M"}).json()
    resp = client.post("/relationships", json={
        "source_type": "requirement",
        "source_id": req["id"],
        "relationship_type": "tracks",
        "target_type": "milestone",
        "target_id": ms["id"],
    })
    assert resp.status_code == 201
    assert resp.json()["source_type"] == "requirement"
    assert resp.json()["display_id"].startswith("REL-")


def test_requirement_appears_in_relationship_picker(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    req = client.post(f"/programs/{prog['id']}/requirements", json={"title": "My Requirement"}).json()
    resp = client.get(f"/programs/{prog['id']}/view")
    assert resp.status_code == 200
    assert req["display_id"] in resp.text
    assert "My Requirement" in resp.text


def test_requirement_relationship_shown_on_detail_page(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    req = client.post(f"/programs/{prog['id']}/requirements", json={"title": "Requirement"}).json()
    dec = client.post(f"/programs/{prog['id']}/decisions", json={"title": "Decision"}).json()
    client.post("/relationships", json={
        "source_type": "requirement", "source_id": req["id"],
        "relationship_type": "relates_to", "target_type": "decision", "target_id": dec["id"],
    })
    resp = client.get(f"/programs/{prog['id']}/view")
    assert resp.status_code == 200
    assert req["display_id"] in resp.text
    assert "relates_to" in resp.text


def test_program_relationships_includes_requirement_relationships(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    req = client.post(f"/programs/{prog['id']}/requirements", json={"title": "R"}).json()
    wi = client.post(
        f"/programs/{prog['id']}/work-items",
        json={"title": "WI", "status": "open", "priority": "medium"},
    ).json()
    client.post("/relationships", json={
        "source_type": "requirement", "source_id": req["id"],
        "relationship_type": "depends_on", "target_type": "work_item", "target_id": wi["id"],
    })
    rels = client.get(f"/programs/{prog['id']}/relationships").json()
    assert len(rels) == 1
    assert rels[0]["source_type"] == "requirement"
