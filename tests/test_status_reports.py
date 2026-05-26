"""Tests for StatusReport model, API, domain logic, and UI."""

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.domain.health import compute_suggested_health
from app.models.program_status import seed_default_program_statuses


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


# ── Domain: compute_suggested_health ─────────────────────────────────────────

def _prog(is_operational=True, work_items=(), dependencies=(), risks=()):
    return SimpleNamespace(
        program_status=SimpleNamespace(is_operational=is_operational),
        work_items=list(work_items),
        dependencies=list(dependencies),
        risks=list(risks),
    )


def _wi(status="open", due_date=None, updated_at=None):
    return SimpleNamespace(
        status=status,
        due_date=due_date,
        updated_at=updated_at or datetime.now(timezone.utc),
        last_touched_at=None,
    )


def _dep(status="open", blocking_level="medium", due_date=None, last_confirmation_at=None):
    return SimpleNamespace(
        status=status, blocking_level=blocking_level,
        due_date=due_date, last_confirmation_at=last_confirmation_at,
    )


def _risk(status="open", severity="medium", last_reviewed_at=None):
    return SimpleNamespace(status=status, severity=severity, last_reviewed_at=last_reviewed_at)


def test_suggested_health_on_track_for_clean_program() -> None:
    assert compute_suggested_health(_prog()) == "on_track"


def test_suggested_health_on_track_for_inactive_program() -> None:
    assert compute_suggested_health(_prog(is_operational=False)) == "on_track"


def test_suggested_health_at_risk_for_needs_attention() -> None:
    p = _prog(work_items=[_wi(status="blocked")])
    assert compute_suggested_health(p) == "at_risk"


def test_suggested_health_at_risk_for_at_risk_state() -> None:
    p = _prog(risks=[_risk(severity="critical")])
    assert compute_suggested_health(p) == "at_risk"


def test_suggested_health_off_track() -> None:
    now = datetime.now(timezone.utc)
    today = now.date()
    p = _prog(
        dependencies=[_dep(blocking_level="critical", due_date=today - timedelta(days=1))]
    )
    assert compute_suggested_health(p) == "off_track"


# ── API: CRUD ─────────────────────────────────────────────────────────────────

def test_create_status_report(client) -> None:
    program = client.post("/programs", json={"name": "Alpha"}).json()

    response = client.post(
        f"/programs/{program['id']}/status-reports",
        json={
            "report_date": "2026-05-26",
            "reported_health": "on_track",
            "health_rationale": "No blockers.",
            "summary": "All milestones on schedule.",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["program_id"] == program["id"]
    assert data["report_date"] == "2026-05-26"
    assert data["reported_health"] == "on_track"
    assert data["suggested_health"] in ("on_track", "at_risk", "off_track")
    assert data["health_rationale"] == "No blockers."
    assert data["summary"] == "All milestones on schedule."


def test_create_status_report_minimal(client) -> None:
    program = client.post("/programs", json={"name": "Beta"}).json()

    response = client.post(
        f"/programs/{program['id']}/status-reports",
        json={"report_date": "2026-05-26", "reported_health": "at_risk"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["reported_health"] == "at_risk"
    assert data["health_rationale"] is None
    assert data["summary"] is None


def test_create_status_report_server_computes_suggested_health(client) -> None:
    program = client.post("/programs", json={"name": "Gamma"}).json()
    client.post(
        f"/programs/{program['id']}/work-items",
        json={"title": "Blocker", "status": "blocked"},
    )

    response = client.post(
        f"/programs/{program['id']}/status-reports",
        json={"report_date": "2026-05-26", "reported_health": "on_track"},
    )

    assert response.status_code == 201
    assert response.json()["suggested_health"] == "at_risk"


def test_list_status_reports(client) -> None:
    program = client.post("/programs", json={"name": "Delta"}).json()
    client.post(f"/programs/{program['id']}/status-reports",
                json={"report_date": "2026-05-24", "reported_health": "on_track"})
    client.post(f"/programs/{program['id']}/status-reports",
                json={"report_date": "2026-05-26", "reported_health": "at_risk"})

    response = client.get(f"/programs/{program['id']}/status-reports")

    assert response.status_code == 200
    dates = [r["report_date"] for r in response.json()]
    assert dates == ["2026-05-26", "2026-05-24"]


def test_get_status_report(client) -> None:
    program = client.post("/programs", json={"name": "Epsilon"}).json()
    created = client.post(
        f"/programs/{program['id']}/status-reports",
        json={"report_date": "2026-05-26", "reported_health": "off_track"},
    ).json()

    response = client.get(f"/status-reports/{created['id']}")

    assert response.status_code == 200
    assert response.json()["reported_health"] == "off_track"


def test_update_status_report(client) -> None:
    program = client.post("/programs", json={"name": "Zeta"}).json()
    created = client.post(
        f"/programs/{program['id']}/status-reports",
        json={"report_date": "2026-05-26", "reported_health": "on_track"},
    ).json()

    response = client.patch(
        f"/status-reports/{created['id']}",
        json={"reported_health": "at_risk", "health_rationale": "Found a blocker."},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["reported_health"] == "at_risk"
    assert data["health_rationale"] == "Found a blocker."
    assert data["suggested_health"] == created["suggested_health"]


def test_update_does_not_change_suggested_health(client) -> None:
    program = client.post("/programs", json={"name": "Eta"}).json()
    created = client.post(
        f"/programs/{program['id']}/status-reports",
        json={"report_date": "2026-05-26", "reported_health": "on_track"},
    ).json()
    original_suggested = created["suggested_health"]

    client.patch(f"/status-reports/{created['id']}", json={"reported_health": "off_track"})
    updated = client.get(f"/status-reports/{created['id']}").json()

    assert updated["suggested_health"] == original_suggested


def test_delete_status_report(client) -> None:
    program = client.post("/programs", json={"name": "Theta"}).json()
    created = client.post(
        f"/programs/{program['id']}/status-reports",
        json={"report_date": "2026-05-26", "reported_health": "on_track"},
    ).json()

    response = client.delete(f"/status-reports/{created['id']}")

    assert response.status_code == 204
    assert client.get(f"/status-reports/{created['id']}").status_code == 404


def test_create_status_report_program_not_found(client) -> None:
    response = client.post(
        "/programs/99999/status-reports",
        json={"report_date": "2026-05-26", "reported_health": "on_track"},
    )
    assert response.status_code == 404


def test_list_status_reports_program_not_found(client) -> None:
    assert client.get("/programs/99999/status-reports").status_code == 404


def test_get_status_report_not_found(client) -> None:
    assert client.get("/status-reports/99999").status_code == 404


def test_update_status_report_not_found(client) -> None:
    assert client.patch("/status-reports/99999", json={"reported_health": "on_track"}).status_code == 404


def test_delete_status_report_not_found(client) -> None:
    assert client.delete("/status-reports/99999").status_code == 404


# ── API: Cascade delete ───────────────────────────────────────────────────────

def test_status_reports_deleted_when_program_deleted(client) -> None:
    program = client.post("/programs", json={"name": "Cascade"}).json()
    report = client.post(
        f"/programs/{program['id']}/status-reports",
        json={"report_date": "2026-05-26", "reported_health": "on_track"},
    ).json()

    client.post(f"/programs/{program['id']}/delete")

    assert client.get(f"/status-reports/{report['id']}").status_code == 404


# ── UI: Program detail section ────────────────────────────────────────────────

def test_program_detail_shows_status_reports_section(client) -> None:
    program = client.post("/programs", json={"name": "Report UI Program"}).json()

    response = client.get(f"/programs/{program['id']}/view")

    assert response.status_code == 200
    assert "Status Reports" in response.text
    assert "New Status Report" in response.text


def test_program_detail_shows_no_reports_empty_state(client) -> None:
    program = client.post("/programs", json={"name": "Empty Reports"}).json()

    response = client.get(f"/programs/{program['id']}/view")

    assert "No status reports yet." in response.text


def test_create_status_report_from_ui(client) -> None:
    program = client.post("/programs", json={"name": "UI Create"}).json()

    response = client.post(
        f"/programs/{program['id']}/status-reports/create",
        data={
            "report_date": "2026-05-26",
            "reported_health": "on_track",
            "health_rationale": "Looking good.",
            "summary": "No issues.",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "2026-05-26" in response.text
    assert "On Track" in response.text


def test_update_status_report_from_ui(client) -> None:
    program = client.post("/programs", json={"name": "UI Edit"}).json()
    report = client.post(
        f"/programs/{program['id']}/status-reports",
        json={"report_date": "2026-05-26", "reported_health": "on_track"},
    ).json()

    response = client.post(
        f"/status-reports/{report['id']}/update",
        data={
            "report_date": "2026-05-26",
            "reported_health": "at_risk",
            "health_rationale": "Found a risk.",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    updated = client.get(f"/status-reports/{report['id']}").json()
    assert updated["reported_health"] == "at_risk"
    assert updated["health_rationale"] == "Found a risk."


def test_delete_status_report_from_ui(client) -> None:
    program = client.post("/programs", json={"name": "UI Delete"}).json()
    report = client.post(
        f"/programs/{program['id']}/status-reports",
        json={"report_date": "2026-05-26", "reported_health": "on_track"},
    ).json()

    response = client.post(
        f"/status-reports/{report['id']}/delete",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert client.get(f"/status-reports/{report['id']}").status_code == 404


def test_program_detail_shows_latest_report_first(client) -> None:
    program = client.post("/programs", json={"name": "Report Order"}).json()
    client.post(
        f"/programs/{program['id']}/status-reports",
        json={"report_date": "2026-05-20", "reported_health": "off_track"},
    )
    client.post(
        f"/programs/{program['id']}/status-reports",
        json={"report_date": "2026-05-26", "reported_health": "on_track", "summary": "Latest one"},
    )

    response = client.get(f"/programs/{program['id']}/view")

    text = response.text
    assert text.index("2026-05-26") < text.index("2026-05-20")


def test_program_detail_shows_divergence_indicator(client) -> None:
    program = client.post("/programs", json={"name": "Divergence"}).json()
    client.post(
        f"/programs/{program['id']}/work-items",
        json={"title": "Blocked", "status": "blocked"},
    )
    client.post(
        f"/programs/{program['id']}/status-reports",
        json={"report_date": "2026-05-26", "reported_health": "on_track"},
    )

    response = client.get(f"/programs/{program['id']}/view")

    assert response.status_code == 200
    assert "↑" in response.text


# ── UI: Program list column ───────────────────────────────────────────────────

def test_program_list_shows_no_report_yet(client) -> None:
    client.post("/programs", json={"name": "No Report Program"})

    response = client.get("/")

    assert response.status_code == 200
    assert "No report yet" in response.text


def test_program_list_shows_latest_reported_health(client) -> None:
    program = client.post("/programs", json={"name": "Has Report"}).json()
    client.post(
        f"/programs/{program['id']}/status-reports",
        json={"report_date": "2026-05-26", "reported_health": "at_risk"},
    )

    response = client.get("/")

    assert response.status_code == 200
    assert "At Risk" in response.text


def test_program_list_shows_latest_not_oldest_report(client) -> None:
    program = client.post("/programs", json={"name": "Multi Report"}).json()
    client.post(
        f"/programs/{program['id']}/status-reports",
        json={"report_date": "2026-05-20", "reported_health": "off_track"},
    )
    client.post(
        f"/programs/{program['id']}/status-reports",
        json={"report_date": "2026-05-26", "reported_health": "on_track"},
    )

    response = client.get("/")

    assert response.status_code == 200
    assert "On Track" in response.text
