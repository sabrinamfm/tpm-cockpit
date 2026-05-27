"""Tests for Relationship model, API, and UI integration."""

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.program import Program
from app.models.program_status import seed_default_program_statuses
from app.models.relationship import Relationship
from app.models.risk import Risk
from app.models.work_item import WorkItem


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def db(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        seed_default_program_statuses(session)
        yield session
    Base.metadata.drop_all(engine)


def _program(db, name="Test Program") -> Program:
    status_id = db.execute(
        text("SELECT id FROM program_statuses WHERE slug = 'active' LIMIT 1")
    ).scalar()
    p = Program(name=name, status_id=status_id)
    db.add(p)
    db.flush()
    return p


def _work_item(db, program: Program, title="WI") -> WorkItem:
    wi = WorkItem(program_id=program.id, title=title, status="open", priority="medium")
    db.add(wi)
    db.flush()
    return wi


def _risk(db, program: Program, title="RSK") -> Risk:
    r = Risk(program_id=program.id, title=title, severity="medium", likelihood="possible", status="open")
    db.add(r)
    db.flush()
    return r


# ── API: POST /relationships ───────────────────────────────────────────────────

def test_create_relationship_valid(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    wi = client.post(f"/programs/{prog['id']}/work-items", json={"title": "WI", "status": "open", "priority": "medium"}).json()
    risk = client.post(f"/programs/{prog['id']}/risks", json={"title": "R", "severity": "medium", "likelihood": "possible", "status": "open"}).json()

    resp = client.post("/relationships", json={
        "source_type": "work_item",
        "source_id": wi["id"],
        "relationship_type": "mitigates",
        "target_type": "risk",
        "target_id": risk["id"],
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["source_type"] == "work_item"
    assert body["target_type"] == "risk"
    assert body["relationship_type"] == "mitigates"
    assert body["display_id"].startswith("REL-")


def test_create_relationship_invalid_source_type(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    wi = client.post(f"/programs/{prog['id']}/work-items", json={"title": "WI", "status": "open", "priority": "medium"}).json()

    resp = client.post("/relationships", json={
        "source_type": "not_a_type",
        "source_id": wi["id"],
        "relationship_type": "relates_to",
        "target_type": "work_item",
        "target_id": wi["id"],
    })
    assert resp.status_code == 422


def test_create_relationship_missing_source(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    wi = client.post(f"/programs/{prog['id']}/work-items", json={"title": "WI", "status": "open", "priority": "medium"}).json()

    resp = client.post("/relationships", json={
        "source_type": "work_item",
        "source_id": 99999,
        "relationship_type": "relates_to",
        "target_type": "work_item",
        "target_id": wi["id"],
    })
    assert resp.status_code == 404


def test_create_relationship_missing_target(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    wi = client.post(f"/programs/{prog['id']}/work-items", json={"title": "WI", "status": "open", "priority": "medium"}).json()

    resp = client.post("/relationships", json={
        "source_type": "work_item",
        "source_id": wi["id"],
        "relationship_type": "relates_to",
        "target_type": "risk",
        "target_id": 99999,
    })
    assert resp.status_code == 404


def test_create_relationship_self(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    wi = client.post(f"/programs/{prog['id']}/work-items", json={"title": "WI", "status": "open", "priority": "medium"}).json()

    resp = client.post("/relationships", json={
        "source_type": "work_item",
        "source_id": wi["id"],
        "relationship_type": "relates_to",
        "target_type": "work_item",
        "target_id": wi["id"],
    })
    assert resp.status_code == 422


# ── API: GET /programs/{id}/relationships ─────────────────────────────────────

def test_list_relationships_for_program(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    wi1 = client.post(f"/programs/{prog['id']}/work-items", json={"title": "WI1", "status": "open", "priority": "medium"}).json()
    wi2 = client.post(f"/programs/{prog['id']}/work-items", json={"title": "WI2", "status": "open", "priority": "medium"}).json()
    risk = client.post(f"/programs/{prog['id']}/risks", json={"title": "R", "severity": "medium", "likelihood": "possible", "status": "open"}).json()

    client.post("/relationships", json={
        "source_type": "work_item", "source_id": wi1["id"],
        "relationship_type": "blocks", "target_type": "work_item", "target_id": wi2["id"],
    })
    client.post("/relationships", json={
        "source_type": "work_item", "source_id": wi1["id"],
        "relationship_type": "mitigates", "target_type": "risk", "target_id": risk["id"],
    })

    resp = client.get(f"/programs/{prog['id']}/relationships")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_list_relationships_for_program_not_found(client) -> None:
    resp = client.get("/programs/99999/relationships")
    assert resp.status_code == 404


def test_list_relationships_excludes_other_programs(client) -> None:
    prog_a = client.post("/programs", json={"name": "A"}).json()
    prog_b = client.post("/programs", json={"name": "B"}).json()
    wi_a = client.post(f"/programs/{prog_a['id']}/work-items", json={"title": "WI-A1", "status": "open", "priority": "medium"}).json()
    wi_a2 = client.post(f"/programs/{prog_a['id']}/work-items", json={"title": "WI-A2", "status": "open", "priority": "medium"}).json()
    wi_b = client.post(f"/programs/{prog_b['id']}/work-items", json={"title": "WI-B", "status": "open", "priority": "medium"}).json()
    wi_b2 = client.post(f"/programs/{prog_b['id']}/work-items", json={"title": "WI-B2", "status": "open", "priority": "medium"}).json()

    client.post("/relationships", json={
        "source_type": "work_item", "source_id": wi_a["id"],
        "relationship_type": "blocks", "target_type": "work_item", "target_id": wi_a2["id"],
    })
    client.post("/relationships", json={
        "source_type": "work_item", "source_id": wi_b["id"],
        "relationship_type": "blocks", "target_type": "work_item", "target_id": wi_b2["id"],
    })

    resp_a = client.get(f"/programs/{prog_a['id']}/relationships")
    resp_b = client.get(f"/programs/{prog_b['id']}/relationships")
    assert len(resp_a.json()) == 1
    assert len(resp_b.json()) == 1


# ── API: DELETE /relationships/{id} ──────────────────────────────────────────

def test_delete_relationship(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    wi1 = client.post(f"/programs/{prog['id']}/work-items", json={"title": "WI1", "status": "open", "priority": "medium"}).json()
    wi2 = client.post(f"/programs/{prog['id']}/work-items", json={"title": "WI2", "status": "open", "priority": "medium"}).json()

    rel = client.post("/relationships", json={
        "source_type": "work_item", "source_id": wi1["id"],
        "relationship_type": "relates_to", "target_type": "work_item", "target_id": wi2["id"],
    }).json()

    resp = client.delete(f"/relationships/{rel['id']}")
    assert resp.status_code == 204

    resp2 = client.get(f"/programs/{prog['id']}/relationships")
    assert resp2.json() == []


def test_delete_relationship_not_found(client) -> None:
    resp = client.delete("/relationships/99999")
    assert resp.status_code == 404


# ── UI: program detail page displays relationships ────────────────────────────

def test_relationship_display_on_detail_page(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    wi = client.post(f"/programs/{prog['id']}/work-items", json={"title": "My Work Item", "status": "open", "priority": "medium"}).json()
    risk = client.post(f"/programs/{prog['id']}/risks", json={"title": "My Risk", "severity": "medium", "likelihood": "possible", "status": "open"}).json()

    client.post("/relationships", json={
        "source_type": "work_item", "source_id": wi["id"],
        "relationship_type": "mitigates", "target_type": "risk", "target_id": risk["id"],
    })

    resp = client.get(f"/programs/{prog['id']}/view")
    assert resp.status_code == 200
    html = resp.text
    assert "mitigates" in html
    assert wi["display_id"] in html
    assert risk["display_id"] in html


def test_detail_page_shows_relationship_form_when_objects_exist(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    client.post(f"/programs/{prog['id']}/work-items", json={"title": "WI", "status": "open", "priority": "medium"})

    resp = client.get(f"/programs/{prog['id']}/view")
    assert resp.status_code == 200
    assert "new-relationship" in resp.text
    assert "Add Relationship" in resp.text


def test_detail_page_shows_no_objects_message_when_empty(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()

    resp = client.get(f"/programs/{prog['id']}/view")
    assert resp.status_code == 200
    assert "Add work items" in resp.text


# ── UI: create relationship via form ─────────────────────────────────────────

def test_create_relationship_via_ui(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    wi = client.post(f"/programs/{prog['id']}/work-items", json={"title": "WI", "status": "open", "priority": "medium"}).json()
    risk = client.post(f"/programs/{prog['id']}/risks", json={"title": "R", "severity": "medium", "likelihood": "possible", "status": "open"}).json()

    resp = client.post(
        f"/programs/{prog['id']}/relationships/create",
        data={
            "source_ref": f"work_item:{wi['id']}",
            "relationship_type": "mitigates",
            "target_ref": f"risk:{risk['id']}",
            "note": "important link",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == f"/programs/{prog['id']}/view"

    rels = client.get(f"/programs/{prog['id']}/relationships").json()
    assert len(rels) == 1
    assert rels[0]["note"] == "important link"


def test_create_relationship_via_ui_bad_type_redirects_with_error(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    wi = client.post(f"/programs/{prog['id']}/work-items", json={"title": "WI", "status": "open", "priority": "medium"}).json()
    risk = client.post(f"/programs/{prog['id']}/risks", json={"title": "R", "severity": "medium", "likelihood": "possible", "status": "open"}).json()

    resp = client.post(
        f"/programs/{prog['id']}/relationships/create",
        data={
            "source_ref": f"work_item:{wi['id']}",
            "relationship_type": "not_a_type",
            "target_ref": f"risk:{risk['id']}",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "show_new_relationship=1" in resp.headers["location"]


# ── UI: delete relationship via form ─────────────────────────────────────────

def test_delete_relationship_via_ui(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    wi1 = client.post(f"/programs/{prog['id']}/work-items", json={"title": "WI1", "status": "open", "priority": "medium"}).json()
    wi2 = client.post(f"/programs/{prog['id']}/work-items", json={"title": "WI2", "status": "open", "priority": "medium"}).json()

    rel = client.post("/relationships", json={
        "source_type": "work_item", "source_id": wi1["id"],
        "relationship_type": "relates_to", "target_type": "work_item", "target_id": wi2["id"],
    }).json()

    resp = client.post(
        f"/relationships/{rel['id']}/delete-ui",
        data={"program_id": str(prog["id"])},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == f"/programs/{prog['id']}/view"

    rels = client.get(f"/programs/{prog['id']}/relationships").json()
    assert rels == []
