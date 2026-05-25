"""Tests for Risk model, API, predicates, and morning-view queries."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.domain.attention import risk_is_critical, risk_is_stale
from app.domain.queries import get_critical_risks, get_stale_risks
from app.models.dependency import Dependency
from app.models.program import Program
from app.models.program_status import seed_default_program_statuses
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


def _program(db, name="Test Program", status_slug="active") -> Program:
    status = db.execute(
        text("SELECT id FROM program_statuses WHERE slug = :slug LIMIT 1"),
        {"slug": status_slug},
    ).fetchone()
    p = Program(name=name, status_id=status[0])
    db.add(p)
    db.flush()
    return p


def _risk(db, program: Program, **kwargs) -> Risk:
    defaults = {
        "title": "Risk",
        "severity": "medium",
        "likelihood": "possible",
        "status": "open",
    }
    defaults.update(kwargs)
    r = Risk(program_id=program.id, **defaults)
    db.add(r)
    db.flush()
    return r


# ── API: CRUD ─────────────────────────────────────────────────────────────────

def test_create_risk(client) -> None:
    program = client.post("/programs", json={"name": "Alpha"}).json()

    response = client.post(
        f"/programs/{program['id']}/risks",
        json={
            "title": "Vendor delay",
            "description": "Key vendor may miss deadline.",
            "severity": "high",
            "likelihood": "likely",
            "status": "open",
            "owner": "Sabrina",
            "mitigation": "Identify backup vendor.",
            "target_resolution_date": "2026-07-01",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["program_id"] == program["id"]
    assert data["title"] == "Vendor delay"
    assert data["severity"] == "high"
    assert data["likelihood"] == "likely"
    assert data["status"] == "open"
    assert data["owner"] == "Sabrina"
    assert data["mitigation"] == "Identify backup vendor."
    assert data["target_resolution_date"] == "2026-07-01"
    assert data["last_reviewed_at"] is None


def test_create_risk_defaults(client) -> None:
    program = client.post("/programs", json={"name": "Beta"}).json()

    response = client.post(
        f"/programs/{program['id']}/risks",
        json={"title": "Minimal risk"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["severity"] == "medium"
    assert data["likelihood"] == "possible"
    assert data["status"] == "open"


def test_list_risks(client) -> None:
    program = client.post("/programs", json={"name": "Gamma"}).json()
    client.post(f"/programs/{program['id']}/risks", json={"title": "First"})
    client.post(f"/programs/{program['id']}/risks", json={"title": "Second"})

    response = client.get(f"/programs/{program['id']}/risks")

    assert response.status_code == 200
    assert {r["title"] for r in response.json()} == {"First", "Second"}


def test_get_risk(client) -> None:
    program = client.post("/programs", json={"name": "Delta"}).json()
    created = client.post(
        f"/programs/{program['id']}/risks", json={"title": "Get me"}
    ).json()

    response = client.get(f"/risks/{created['id']}")

    assert response.status_code == 200
    assert response.json()["title"] == "Get me"


def test_update_risk(client) -> None:
    program = client.post("/programs", json={"name": "Epsilon"}).json()
    created = client.post(
        f"/programs/{program['id']}/risks",
        json={"title": "Old title", "severity": "low"},
    ).json()

    response = client.patch(
        f"/risks/{created['id']}",
        json={"title": "New title", "severity": "critical", "status": "monitoring"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "New title"
    assert data["severity"] == "critical"
    assert data["status"] == "monitoring"


def test_delete_risk(client) -> None:
    program = client.post("/programs", json={"name": "Zeta"}).json()
    created = client.post(
        f"/programs/{program['id']}/risks", json={"title": "Delete me"}
    ).json()

    response = client.delete(f"/risks/{created['id']}")

    assert response.status_code == 204
    assert client.get(f"/risks/{created['id']}").status_code == 404


def test_create_risk_program_not_found(client) -> None:
    response = client.post("/programs/99999/risks", json={"title": "Ghost"})
    assert response.status_code == 404


def test_get_risk_not_found(client) -> None:
    assert client.get("/risks/99999").status_code == 404


def test_update_risk_not_found(client) -> None:
    assert client.patch("/risks/99999", json={"title": "X"}).status_code == 404


def test_delete_risk_not_found(client) -> None:
    assert client.delete("/risks/99999").status_code == 404


# ── API: Mark Reviewed ────────────────────────────────────────────────────────

def test_mark_reviewed_sets_last_reviewed_at(client) -> None:
    program = client.post("/programs", json={"name": "Review Test"}).json()
    risk = client.post(
        f"/programs/{program['id']}/risks", json={"title": "Review me"}
    ).json()
    assert risk["last_reviewed_at"] is None

    response = client.post(f"/risks/{risk['id']}/review")

    assert response.status_code == 200
    assert response.json()["last_reviewed_at"] is not None


def test_mark_reviewed_updates_timestamp(client) -> None:
    program = client.post("/programs", json={"name": "Timestamp Test"}).json()
    risk = client.post(
        f"/programs/{program['id']}/risks", json={"title": "Has timestamp"}
    ).json()
    client.post(f"/risks/{risk['id']}/review")
    first_review = client.get(f"/risks/{risk['id']}").json()["last_reviewed_at"]

    client.post(f"/risks/{risk['id']}/review")
    second_review = client.get(f"/risks/{risk['id']}").json()["last_reviewed_at"]

    assert second_review >= first_review


def test_mark_reviewed_not_found(client) -> None:
    assert client.post("/risks/99999/review").status_code == 404


# ── API: Cascade delete ───────────────────────────────────────────────────────

def test_risks_deleted_when_program_deleted(client) -> None:
    program = client.post("/programs", json={"name": "Cascade"}).json()
    risk = client.post(
        f"/programs/{program['id']}/risks", json={"title": "Orphan"}
    ).json()

    client.post(f"/programs/{program['id']}/delete")

    assert client.get(f"/risks/{risk['id']}").status_code == 404


# ── Domain predicates: risk_is_stale ─────────────────────────────────────────

def test_risk_is_stale_when_reviewed_over_14_days_ago() -> None:
    now = datetime(2026, 5, 25, 12, 0, tzinfo=timezone.utc)
    risk = SimpleNamespace(
        status="open",
        last_reviewed_at=now - timedelta(days=15),
        severity="medium",
    )
    assert risk_is_stale(risk, now=now) is True


def test_risk_is_not_stale_when_reviewed_recently() -> None:
    now = datetime(2026, 5, 25, 12, 0, tzinfo=timezone.utc)
    risk = SimpleNamespace(
        status="open",
        last_reviewed_at=now - timedelta(days=3),
        severity="medium",
    )
    assert risk_is_stale(risk, now=now) is False


def test_risk_is_not_stale_when_never_reviewed() -> None:
    now = datetime(2026, 5, 25, 12, 0, tzinfo=timezone.utc)
    risk = SimpleNamespace(status="open", last_reviewed_at=None, severity="medium")
    assert risk_is_stale(risk, now=now) is False


def test_risk_is_not_stale_when_resolved() -> None:
    now = datetime(2026, 5, 25, 12, 0, tzinfo=timezone.utc)
    risk = SimpleNamespace(
        status="resolved",
        last_reviewed_at=now - timedelta(days=30),
        severity="medium",
    )
    assert risk_is_stale(risk, now=now) is False


def test_risk_is_not_stale_when_accepted() -> None:
    now = datetime(2026, 5, 25, 12, 0, tzinfo=timezone.utc)
    risk = SimpleNamespace(
        status="accepted",
        last_reviewed_at=now - timedelta(days=30),
        severity="medium",
    )
    assert risk_is_stale(risk, now=now) is False


# ── Domain predicates: risk_is_critical ──────────────────────────────────────

def test_risk_is_critical_for_high_severity_open() -> None:
    risk = SimpleNamespace(severity="high", status="open")
    assert risk_is_critical(risk) is True


def test_risk_is_critical_for_critical_severity_open() -> None:
    risk = SimpleNamespace(severity="critical", status="open")
    assert risk_is_critical(risk) is True


def test_risk_is_critical_for_critical_severity_monitoring() -> None:
    risk = SimpleNamespace(severity="critical", status="monitoring")
    assert risk_is_critical(risk) is True


def test_risk_is_not_critical_for_medium_severity() -> None:
    risk = SimpleNamespace(severity="medium", status="open")
    assert risk_is_critical(risk) is False


def test_risk_is_not_critical_when_resolved() -> None:
    risk = SimpleNamespace(severity="critical", status="resolved")
    assert risk_is_critical(risk) is False


def test_risk_is_not_critical_when_accepted() -> None:
    risk = SimpleNamespace(severity="high", status="accepted")
    assert risk_is_critical(risk) is False


# ── Morning queries: get_critical_risks ──────────────────────────────────────

def test_get_critical_risks_returns_high_and_critical(db) -> None:
    p = _program(db)
    _risk(db, p, title="Critical open", severity="critical", status="open")
    _risk(db, p, title="High monitoring", severity="high", status="monitoring")
    _risk(db, p, title="Medium open", severity="medium", status="open")
    db.commit()

    result = get_critical_risks(db)

    titles = {r.title for r in result}
    assert "Critical open" in titles
    assert "High monitoring" in titles
    assert "Medium open" not in titles


def test_get_critical_risks_excludes_resolved_and_accepted(db) -> None:
    p = _program(db)
    _risk(db, p, title="Critical resolved", severity="critical", status="resolved")
    _risk(db, p, title="High accepted", severity="high", status="accepted")
    db.commit()

    assert get_critical_risks(db) == []


def test_get_critical_risks_excludes_non_operational_programs(db) -> None:
    active_p = _program(db, name="Active", status_slug="active")
    _risk(db, active_p, title="Active critical", severity="critical", status="open")
    archived_p = _program(db, name="Archived", status_slug="archived")
    _risk(db, archived_p, title="Archived critical", severity="critical", status="open")
    db.commit()

    result = get_critical_risks(db)

    titles = {r.title for r in result}
    assert "Active critical" in titles
    assert "Archived critical" not in titles


def test_get_critical_risks_empty(db) -> None:
    p = _program(db)
    _risk(db, p, severity="low", status="open")
    db.commit()

    assert get_critical_risks(db) == []


# ── Morning queries: get_stale_risks ─────────────────────────────────────────

def test_get_stale_risks_returns_old_reviews(db) -> None:
    now = datetime(2026, 5, 25, 12, 0, tzinfo=timezone.utc)
    p = _program(db)
    stale = _risk(db, p, title="Stale risk", status="open")
    stale.last_reviewed_at = now - timedelta(days=15)
    fresh = _risk(db, p, title="Fresh risk", status="open")
    fresh.last_reviewed_at = now - timedelta(days=3)
    db.commit()

    result = get_stale_risks(db, now=now)

    assert len(result) == 1
    assert result[0].title == "Stale risk"


def test_get_stale_risks_ignores_never_reviewed(db) -> None:
    now = datetime(2026, 5, 25, 12, 0, tzinfo=timezone.utc)
    p = _program(db)
    _risk(db, p, status="open")
    db.commit()

    assert get_stale_risks(db, now=now) == []


def test_get_stale_risks_excludes_resolved_and_accepted(db) -> None:
    now = datetime(2026, 5, 25, 12, 0, tzinfo=timezone.utc)
    p = _program(db)
    resolved = _risk(db, p, status="resolved")
    resolved.last_reviewed_at = now - timedelta(days=30)
    accepted = _risk(db, p, status="accepted")
    accepted.last_reviewed_at = now - timedelta(days=30)
    db.commit()

    assert get_stale_risks(db, now=now) == []


def test_get_stale_risks_excludes_non_operational_programs(db) -> None:
    now = datetime(2026, 5, 25, 12, 0, tzinfo=timezone.utc)
    active_p = _program(db, name="Active", status_slug="active")
    active_risk = _risk(db, active_p, title="Active stale")
    active_risk.last_reviewed_at = now - timedelta(days=20)
    completed_p = _program(db, name="Completed", status_slug="completed")
    completed_risk = _risk(db, completed_p, title="Completed stale")
    completed_risk.last_reviewed_at = now - timedelta(days=20)
    db.commit()

    result = get_stale_risks(db, now=now)

    titles = {r.title for r in result}
    assert "Active stale" in titles
    assert "Completed stale" not in titles


# ── UI: Program detail Risks section ─────────────────────────────────────────

def test_program_detail_shows_risks_section(client) -> None:
    program = client.post("/programs", json={"name": "Risk UI Program"}).json()

    response = client.get(f"/programs/{program['id']}/view")

    assert response.status_code == 200
    assert "Risks" in response.text
    assert "New Risk" in response.text


def test_create_risk_from_ui(client) -> None:
    program = client.post("/programs", json={"name": "UI Risk Program"}).json()

    response = client.post(
        f"/programs/{program['id']}/risks/create",
        data={
            "title": "UI Risk",
            "severity": "high",
            "likelihood": "likely",
            "status": "open",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "UI Risk" in response.text


def test_review_risk_from_ui(client) -> None:
    program = client.post("/programs", json={"name": "Review UI"}).json()
    risk = client.post(
        f"/programs/{program['id']}/risks",
        json={"title": "Reviewable"},
    ).json()
    assert risk["last_reviewed_at"] is None

    response = client.post(f"/risks/{risk['id']}/review-ui", follow_redirects=True)

    assert response.status_code == 200
    updated = client.get(f"/risks/{risk['id']}").json()
    assert updated["last_reviewed_at"] is not None


def test_delete_risk_from_ui(client) -> None:
    program = client.post("/programs", json={"name": "Delete Risk UI"}).json()
    risk = client.post(
        f"/programs/{program['id']}/risks",
        json={"title": "To delete"},
    ).json()

    response = client.post(f"/risks/{risk['id']}/delete", follow_redirects=True)

    assert response.status_code == 200
    assert client.get(f"/risks/{risk['id']}").status_code == 404


# ── UI: Morning view ──────────────────────────────────────────────────────────

def test_morning_view_shows_critical_risks_section(client) -> None:
    response = client.get("/morning")
    assert response.status_code == 200
    assert "Critical Risks" in response.text


def test_morning_view_shows_stale_risks_section(client) -> None:
    response = client.get("/morning")
    assert response.status_code == 200
    assert "Stale Risks" in response.text
