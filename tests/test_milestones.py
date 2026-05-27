"""Tests for launch_date on Program and the Milestone model, API, and UI."""

import pytest


# ── Program launch_date ───────────────────────────────────────────────────────

def test_create_program_with_launch_date(client) -> None:
    resp = client.post("/programs", json={"name": "P", "launch_date": "2026-09-01"})
    assert resp.status_code == 201
    assert resp.json()["launch_date"] == "2026-09-01"


def test_create_program_without_launch_date(client) -> None:
    resp = client.post("/programs", json={"name": "P"})
    assert resp.status_code == 201
    assert resp.json()["launch_date"] is None


def test_update_program_launch_date(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    resp = client.patch(f"/programs/{prog['id']}", json={"launch_date": "2026-12-01"})
    assert resp.status_code == 200
    assert resp.json()["launch_date"] == "2026-12-01"


def test_program_list_shows_launch_date(client) -> None:
    client.post("/programs", json={"name": "P", "launch_date": "2026-09-15"})
    resp = client.get("/")
    assert resp.status_code == 200
    assert "2026-09-15" in resp.text


def test_program_detail_shows_launch_date(client) -> None:
    prog = client.post("/programs", json={"name": "P", "launch_date": "2026-09-15"}).json()
    resp = client.get(f"/programs/{prog['id']}/view")
    assert resp.status_code == 200
    assert "2026-09-15" in resp.text


def test_create_program_via_ui_with_launch_date(client) -> None:
    resp = client.post(
        "/programs/create",
        data={"name": "UI Program", "launch_date": "2026-10-01"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    programs = client.get("/programs").json()
    match = next((p for p in programs if p["name"] == "UI Program"), None)
    assert match is not None
    assert match["launch_date"] == "2026-10-01"


# ── Milestone API ─────────────────────────────────────────────────────────────

def test_create_milestone_valid(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    resp = client.post(
        f"/programs/{prog['id']}/milestones",
        json={"title": "Beta Release", "status": "planned", "target_date": "2026-08-01"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "Beta Release"
    assert body["status"] == "planned"
    assert body["target_date"] == "2026-08-01"
    assert body["display_id"].startswith("MS-")
    assert body["program_id"] == prog["id"]


def test_create_milestone_invalid_status(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    resp = client.post(
        f"/programs/{prog['id']}/milestones",
        json={"title": "M", "status": "not_a_status"},
    )
    assert resp.status_code == 422


def test_create_milestone_program_not_found(client) -> None:
    resp = client.post("/milestones/99999", json={"title": "M"})
    assert resp.status_code in (404, 405)


def test_list_milestones(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    client.post(f"/programs/{prog['id']}/milestones", json={"title": "M1", "target_date": "2026-07-01"})
    client.post(f"/programs/{prog['id']}/milestones", json={"title": "M2", "target_date": "2026-08-01"})
    resp = client.get(f"/programs/{prog['id']}/milestones")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_list_milestones_program_not_found(client) -> None:
    resp = client.get("/programs/99999/milestones")
    assert resp.status_code == 404


def test_get_milestone(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    ms = client.post(f"/programs/{prog['id']}/milestones", json={"title": "M"}).json()
    resp = client.get(f"/milestones/{ms['id']}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "M"


def test_get_milestone_not_found(client) -> None:
    assert client.get("/milestones/99999").status_code == 404


def test_update_milestone(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    ms = client.post(f"/programs/{prog['id']}/milestones", json={"title": "M", "status": "planned"}).json()
    resp = client.patch(f"/milestones/{ms['id']}", json={"status": "achieved", "title": "M Done"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "achieved"
    assert resp.json()["title"] == "M Done"


def test_delete_milestone(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    ms = client.post(f"/programs/{prog['id']}/milestones", json={"title": "M"}).json()
    assert client.delete(f"/milestones/{ms['id']}").status_code == 204
    assert client.get(f"/milestones/{ms['id']}").status_code == 404


def test_delete_milestone_not_found(client) -> None:
    assert client.delete("/milestones/99999").status_code == 404


def test_milestone_display_ids_are_unique(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    ms1 = client.post(f"/programs/{prog['id']}/milestones", json={"title": "M1"}).json()
    ms2 = client.post(f"/programs/{prog['id']}/milestones", json={"title": "M2"}).json()
    assert ms1["display_id"] != ms2["display_id"]
    assert ms1["display_id"].startswith("MS-")
    assert ms2["display_id"].startswith("MS-")


# ── Milestone UI ──────────────────────────────────────────────────────────────

def test_program_detail_shows_milestones_section(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    resp = client.get(f"/programs/{prog['id']}/view")
    assert resp.status_code == 200
    assert "Milestones" in resp.text
    assert "new-milestone" in resp.text


def test_program_detail_shows_milestone_row(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    client.post(
        f"/programs/{prog['id']}/milestones",
        json={"title": "Beta Launch", "status": "planned", "target_date": "2026-08-01"},
    )
    resp = client.get(f"/programs/{prog['id']}/view")
    assert resp.status_code == 200
    assert "Beta Launch" in resp.text
    assert "Planned" in resp.text
    assert "2026-08-01" in resp.text


def test_create_milestone_via_ui(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    resp = client.post(
        f"/programs/{prog['id']}/milestones/create",
        data={"title": "RC1", "status": "planned", "target_date": "2026-09-01"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == f"/programs/{prog['id']}/view"
    milestones = client.get(f"/programs/{prog['id']}/milestones").json()
    assert len(milestones) == 1
    assert milestones[0]["title"] == "RC1"


def test_create_milestone_via_ui_missing_title(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    resp = client.post(
        f"/programs/{prog['id']}/milestones/create",
        data={"title": "", "status": "planned"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "show_new_milestone=1" in resp.headers["location"]


def test_achieve_milestone_via_ui(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    ms = client.post(
        f"/programs/{prog['id']}/milestones",
        json={"title": "M", "status": "in_progress"},
    ).json()
    resp = client.post(f"/milestones/{ms['id']}/achieve-ui", follow_redirects=False)
    assert resp.status_code == 303
    assert client.get(f"/milestones/{ms['id']}").json()["status"] == "achieved"


def test_delete_milestone_via_ui(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    ms = client.post(f"/programs/{prog['id']}/milestones", json={"title": "M"}).json()
    resp = client.post(f"/milestones/{ms['id']}/delete", follow_redirects=False)
    assert resp.status_code == 303
    assert client.get(f"/milestones/{ms['id']}").status_code == 404


def test_edit_milestone_panel_opens_inline(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    ms = client.post(f"/programs/{prog['id']}/milestones", json={"title": "Inline MS"}).json()
    resp = client.get(f"/programs/{prog['id']}/view?edit_milestone_id={ms['id']}")
    assert resp.status_code == 200
    assert '<details id="edit-milestone" class="collapsible-panel" open>' in resp.text
    assert "Inline MS" in resp.text


# ── Milestone + Relationship integration ─────────────────────────────────────

def test_create_relationship_with_milestone(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    ms = client.post(f"/programs/{prog['id']}/milestones", json={"title": "M"}).json()
    wi = client.post(
        f"/programs/{prog['id']}/work-items",
        json={"title": "WI", "status": "open", "priority": "medium"},
    ).json()
    resp = client.post("/relationships", json={
        "source_type": "milestone",
        "source_id": ms["id"],
        "relationship_type": "tracks",
        "target_type": "work_item",
        "target_id": wi["id"],
    })
    assert resp.status_code == 201
    assert resp.json()["source_type"] == "milestone"
    assert resp.json()["display_id"].startswith("REL-")


def test_milestone_appears_in_relationship_picker(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    ms = client.post(f"/programs/{prog['id']}/milestones", json={"title": "My Milestone"}).json()
    resp = client.get(f"/programs/{prog['id']}/view")
    assert resp.status_code == 200
    assert ms["display_id"] in resp.text
    assert "My Milestone" in resp.text


def test_milestone_relationship_shown_on_detail_page(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    ms = client.post(f"/programs/{prog['id']}/milestones", json={"title": "Milestone"}).json()
    wi = client.post(
        f"/programs/{prog['id']}/work-items",
        json={"title": "WI", "status": "open", "priority": "medium"},
    ).json()
    client.post("/relationships", json={
        "source_type": "milestone", "source_id": ms["id"],
        "relationship_type": "tracks", "target_type": "work_item", "target_id": wi["id"],
    })
    resp = client.get(f"/programs/{prog['id']}/view")
    assert resp.status_code == 200
    assert ms["display_id"] in resp.text
    assert "tracks" in resp.text


def test_program_relationships_includes_milestone_relationships(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    ms = client.post(f"/programs/{prog['id']}/milestones", json={"title": "M"}).json()
    wi = client.post(
        f"/programs/{prog['id']}/work-items",
        json={"title": "WI", "status": "open", "priority": "medium"},
    ).json()
    client.post("/relationships", json={
        "source_type": "milestone", "source_id": ms["id"],
        "relationship_type": "tracks", "target_type": "work_item", "target_id": wi["id"],
    })
    rels = client.get(f"/programs/{prog['id']}/relationships").json()
    assert len(rels) == 1
    assert rels[0]["source_type"] == "milestone"
