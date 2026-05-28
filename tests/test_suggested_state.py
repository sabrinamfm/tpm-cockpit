"""Tests for suggested_state on StatusReport (M3 from architecture review).

Covers:
- New reports store suggested_state alongside suggested_health
- suggested_state preserves inactive separately from on_track
- suggested_state preserves needs_attention separately from at_risk
- Normal edits do not recompute suggested_state
- Explicit recalculation updates both suggested_state and suggested_health
- Reports with null suggested_state render safely
"""

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_program(client, name="P") -> dict:
    return client.post("/programs", json={"name": name}).json()


def _make_work_item(client, program_id: int, **kwargs) -> dict:
    payload = {"title": "WI", "status": "open", "priority": "medium", **kwargs}
    return client.post(f"/programs/{program_id}/work-items", json=payload).json()


def _make_report(client, program_id: int, health="on_track") -> dict:
    return client.post(
        f"/programs/{program_id}/status-reports",
        json={"report_date": "2026-01-01", "reported_health": health, "summary": "s"},
    ).json()


def _get_report(client, report_id: int) -> dict:
    return client.get(f"/status-reports/{report_id}").json()


# ── API: new report stores suggested_state ────────────────────────────────────

def test_new_report_stores_suggested_state(client):
    prog = _make_program(client)
    report = _make_report(client, prog["id"])
    assert "suggested_state" in report
    assert report["suggested_state"] is not None


def test_suggested_state_on_clean_program_is_on_track(client):
    prog = _make_program(client)
    report = _make_report(client, prog["id"])
    assert report["suggested_state"] == "on_track"
    assert report["suggested_health"] == "on_track"


def test_suggested_state_inactive_preserved_separately_from_on_track(client):
    """inactive program → suggested_state='inactive', suggested_health='on_track'."""
    inactive_prog = client.post("/programs", json={"name": "Inactive"}).json()
    # "paused" is a non-operational status (is_operational=False)
    client.patch(f"/programs/{inactive_prog['id']}", json={"status": "paused"})

    report = _make_report(client, inactive_prog["id"])
    assert report["suggested_state"] == "inactive"
    assert report["suggested_health"] == "on_track"  # 3-state mapping collapses inactive → on_track


def test_suggested_state_needs_attention_preserved_separately_from_at_risk(client):
    """Single blocked work item → needs_attention, but suggested_health maps it to at_risk."""
    prog = _make_program(client)
    _make_work_item(client, prog["id"], status="blocked")

    report = _make_report(client, prog["id"])
    assert report["suggested_state"] == "needs_attention"
    assert report["suggested_health"] == "at_risk"  # 3-state mapping collapses needs_attention → at_risk


def test_suggested_state_at_risk_stored_directly(client):
    """Program with a critical dependency (not overdue) → at_risk in both fields."""
    prog = _make_program(client)
    client.post(
        f"/programs/{prog['id']}/dependencies",
        json={"title": "D", "status": "open", "blocking_level": "critical"},
    )
    report = _make_report(client, prog["id"])
    assert report["suggested_state"] == "at_risk"
    assert report["suggested_health"] == "at_risk"


def test_suggested_state_off_track_stored_directly(client):
    """Overdue critical dependency → off_track in both fields."""
    prog = _make_program(client)
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    client.post(
        f"/programs/{prog['id']}/dependencies",
        json={"title": "D", "status": "open", "blocking_level": "critical", "due_date": yesterday},
    )
    report = _make_report(client, prog["id"])
    assert report["suggested_state"] == "off_track"
    assert report["suggested_health"] == "off_track"


# ── API: normal edit does not recompute suggested_state ───────────────────────

def test_normal_edit_does_not_change_suggested_state(client):
    prog = _make_program(client)
    _make_work_item(client, prog["id"], status="blocked")
    report = _make_report(client, prog["id"])
    original_state = report["suggested_state"]
    assert original_state == "needs_attention"

    # Resolve the blocked item so health would change if recomputed
    client.patch(f"/work-items/{_get_all_work_items(client, prog['id'])[0]['id']}", json={"status": "done"})

    # Normal PATCH does not recompute
    updated = client.patch(f"/status-reports/{report['id']}", json={"summary": "updated"}).json()
    assert updated["suggested_state"] == original_state


def _get_all_work_items(client, program_id: int) -> list:
    return client.get(f"/programs/{program_id}/work-items").json()


# ── UI: create stores suggested_state ────────────────────────────────────────

def test_ui_create_stores_suggested_state(client):
    prog = _make_program(client)
    _make_work_item(client, prog["id"], status="blocked")

    resp = client.post(
        f"/programs/{prog['id']}/status-reports/create",
        data={"report_date": "2026-01-01", "reported_health": "on_track"},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    reports = client.get(f"/programs/{prog['id']}/status-reports").json()
    assert len(reports) == 1
    assert reports[0]["suggested_state"] == "needs_attention"


# ── UI: recalculate updates both suggested_state and suggested_health ─────────

def test_ui_recalculate_updates_suggested_state(client):
    prog = _make_program(client)
    report = _make_report(client, prog["id"])
    assert report["suggested_state"] == "on_track"
    assert report["suggested_health"] == "on_track"

    # Now make the program unhealthy
    _make_work_item(client, prog["id"], status="blocked")

    resp = client.post(
        f"/status-reports/{report['id']}/recalculate-health",
        follow_redirects=False,
    )
    assert resp.status_code == 303

    refreshed = _get_report(client, report["id"])
    assert refreshed["suggested_state"] == "needs_attention"
    assert refreshed["suggested_health"] == "at_risk"


def test_ui_recalculate_also_updates_suggested_health(client):
    prog = _make_program(client)
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    client.post(
        f"/programs/{prog['id']}/dependencies",
        json={"title": "D", "status": "open", "blocking_level": "critical", "due_date": yesterday},
    )
    report = _make_report(client, prog["id"])
    assert report["suggested_state"] == "off_track"
    assert report["suggested_health"] == "off_track"

    # Resolve the dependency
    deps = client.get(f"/programs/{prog['id']}/dependencies").json()
    client.patch(f"/dependencies/{deps[0]['id']}", json={"status": "resolved"})

    client.post(f"/status-reports/{report['id']}/recalculate-health", follow_redirects=False)

    refreshed = _get_report(client, report["id"])
    assert refreshed["suggested_state"] == "on_track"
    assert refreshed["suggested_health"] == "on_track"


# ── Reports with null suggested_state render safely ───────────────────────────

def test_report_with_null_suggested_state_returns_in_api(client):
    """A report created before M3 (suggested_state=NULL) is returned without error."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    from app.db.base import Base
    from app.db.session import get_db
    from app.main import app
    from app.models.program_status import seed_default_program_statuses
    import tempfile

    # Create a report via API then NULL-out suggested_state via direct SQL
    prog = _make_program(client)
    report = _make_report(client, prog["id"])

    # Access the db override to run direct SQL
    with next(app.dependency_overrides[get_db]()) as db:
        db.execute(
            text("UPDATE status_reports SET suggested_state = NULL WHERE id = :id"),
            {"id": report["id"]},
        )
        db.commit()

    fetched = _get_report(client, report["id"])
    assert fetched["suggested_state"] is None
    assert fetched["id"] == report["id"]


def test_report_with_null_suggested_state_renders_in_ui(client):
    """Status report detail page loads without error when suggested_state is NULL."""
    from sqlalchemy import text
    from app.db.session import get_db
    from app.main import app

    prog = _make_program(client)
    report = _make_report(client, prog["id"])

    with next(app.dependency_overrides[get_db]()) as db:
        db.execute(
            text("UPDATE status_reports SET suggested_state = NULL WHERE id = :id"),
            {"id": report["id"]},
        )
        db.commit()

    resp = client.get(f"/status-reports/{report['id']}/view")
    assert resp.status_code == 200
