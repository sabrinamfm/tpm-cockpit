"""Unit tests for program_health_state and program_health_evidence."""

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.domain.health import (
    HEALTH_AT_RISK,
    HEALTH_INACTIVE,
    HEALTH_NEEDS_ATTENTION,
    HEALTH_OFF_TRACK,
    HEALTH_ON_TRACK,
    program_health_evidence,
    program_health_state,
)

NOW = datetime(2026, 5, 25, 12, 0, tzinfo=timezone.utc)
TODAY = NOW.date()

RECENT = NOW - timedelta(days=1)
STALE_WI = NOW - timedelta(days=8)      # > 7 days
STALE_DEP = NOW - timedelta(days=15)    # > 14 days
STALE_RISK = NOW - timedelta(days=15)   # > 14 days


def _wi(status="open", due_date=None, updated_at=None):
    return SimpleNamespace(
        status=status,
        due_date=due_date,
        updated_at=updated_at or RECENT,
        last_touched_at=None,
    )


def _dep(status="open", blocking_level="medium", due_date=None, last_confirmation_at=None):
    return SimpleNamespace(
        status=status,
        blocking_level=blocking_level,
        due_date=due_date,
        last_confirmation_at=last_confirmation_at,
    )


def _risk(status="open", severity="medium", last_reviewed_at=None):
    return SimpleNamespace(status=status, severity=severity, last_reviewed_at=last_reviewed_at)


def _program(work_items=(), dependencies=(), risks=(), is_operational=True):
    return SimpleNamespace(
        work_items=list(work_items),
        dependencies=list(dependencies),
        risks=list(risks),
        program_status=SimpleNamespace(is_operational=is_operational),
    )


# ── inactive ──────────────────────────────────────────────────────────────────

def test_inactive_when_not_operational() -> None:
    p = _program(is_operational=False)
    assert program_health_state(p, now=NOW) == HEALTH_INACTIVE


def test_inactive_even_with_signals_when_not_operational() -> None:
    p = _program(
        work_items=[_wi(status="blocked")],
        is_operational=False,
    )
    assert program_health_state(p, now=NOW) == HEALTH_INACTIVE


# ── on_track ──────────────────────────────────────────────────────────────────

def test_on_track_with_no_signals() -> None:
    p = _program()
    assert program_health_state(p, now=NOW) == HEALTH_ON_TRACK


def test_on_track_with_empty_program() -> None:
    p = _program(work_items=[], dependencies=[], risks=[])
    assert program_health_state(p, now=NOW) == HEALTH_ON_TRACK


# ── needs_attention: single signals ──────────────────────────────────────────

def test_needs_attention_for_blocked_work_item() -> None:
    p = _program(work_items=[_wi(status="blocked")])
    assert program_health_state(p, now=NOW) == HEALTH_NEEDS_ATTENTION


def test_needs_attention_for_overdue_work_item() -> None:
    p = _program(work_items=[_wi(due_date=TODAY - timedelta(days=1))])
    assert program_health_state(p, now=NOW) == HEALTH_NEEDS_ATTENTION


def test_needs_attention_for_stale_work_item() -> None:
    p = _program(work_items=[_wi(updated_at=STALE_WI)])
    assert program_health_state(p, now=NOW) == HEALTH_NEEDS_ATTENTION


def test_needs_attention_for_blocked_dependency() -> None:
    p = _program(dependencies=[_dep(status="blocked")])
    assert program_health_state(p, now=NOW) == HEALTH_NEEDS_ATTENTION


def test_needs_attention_for_stale_dependency() -> None:
    p = _program(dependencies=[_dep(last_confirmation_at=STALE_DEP)])
    assert program_health_state(p, now=NOW) == HEALTH_NEEDS_ATTENTION


def test_needs_attention_for_stale_risk() -> None:
    p = _program(risks=[_risk(last_reviewed_at=STALE_RISK)])
    assert program_health_state(p, now=NOW) == HEALTH_NEEDS_ATTENTION


# ── at_risk: critical dep or risk ─────────────────────────────────────────────

def test_at_risk_for_critical_dependency() -> None:
    p = _program(dependencies=[_dep(blocking_level="critical")])
    assert program_health_state(p, now=NOW) == HEALTH_AT_RISK


def test_at_risk_for_critical_risk() -> None:
    p = _program(risks=[_risk(severity="critical")])
    assert program_health_state(p, now=NOW) == HEALTH_AT_RISK


def test_at_risk_for_high_severity_risk() -> None:
    p = _program(risks=[_risk(severity="high")])
    assert program_health_state(p, now=NOW) == HEALTH_AT_RISK


def test_at_risk_for_three_attention_signals() -> None:
    p = _program(
        work_items=[_wi(status="blocked"), _wi(due_date=TODAY - timedelta(days=1))],
        dependencies=[_dep(status="blocked")],
    )
    assert program_health_state(p, now=NOW) == HEALTH_AT_RISK


def test_needs_attention_for_only_two_signals() -> None:
    p = _program(
        work_items=[_wi(status="blocked")],
        dependencies=[_dep(status="blocked")],
    )
    assert program_health_state(p, now=NOW) == HEALTH_NEEDS_ATTENTION


# ── off_track: overdue critical dep ───────────────────────────────────────────

def test_off_track_for_overdue_critical_dependency() -> None:
    p = _program(
        dependencies=[_dep(blocking_level="critical", due_date=TODAY - timedelta(days=1))]
    )
    assert program_health_state(p, now=NOW) == HEALTH_OFF_TRACK


def test_not_off_track_when_critical_dep_not_overdue() -> None:
    p = _program(
        dependencies=[_dep(blocking_level="critical", due_date=TODAY + timedelta(days=5))]
    )
    assert program_health_state(p, now=NOW) == HEALTH_AT_RISK


def test_not_off_track_for_resolved_overdue_critical_dep() -> None:
    p = _program(
        dependencies=[_dep(blocking_level="critical", due_date=TODAY - timedelta(days=1), status="resolved")]
    )
    assert program_health_state(p, now=NOW) == HEALTH_ON_TRACK


# ── off_track: critical risk + blocked dep ────────────────────────────────────

def test_off_track_for_critical_risk_and_blocked_dep() -> None:
    p = _program(
        dependencies=[_dep(status="blocked")],
        risks=[_risk(severity="critical")],
    )
    assert program_health_state(p, now=NOW) == HEALTH_OFF_TRACK


def test_off_track_for_high_risk_and_blocked_dep() -> None:
    p = _program(
        dependencies=[_dep(status="blocked")],
        risks=[_risk(severity="high")],
    )
    assert program_health_state(p, now=NOW) == HEALTH_OFF_TRACK


def test_at_risk_for_critical_risk_without_blocked_dep() -> None:
    p = _program(risks=[_risk(severity="critical")])
    assert program_health_state(p, now=NOW) == HEALTH_AT_RISK


# ── off_track: two of {critical_dep, critical_risk, blocked_dep} ─────────────

def test_off_track_for_critical_dep_and_critical_risk() -> None:
    p = _program(
        dependencies=[_dep(blocking_level="critical")],
        risks=[_risk(severity="critical")],
    )
    assert program_health_state(p, now=NOW) == HEALTH_OFF_TRACK


def test_off_track_for_critical_dep_and_blocked_dep() -> None:
    p = _program(
        dependencies=[
            _dep(blocking_level="critical"),
            _dep(status="blocked"),
        ]
    )
    assert program_health_state(p, now=NOW) == HEALTH_OFF_TRACK


# ── evidence: counts and pluralization ───────────────────────────────────────

def test_evidence_empty_for_on_track_program() -> None:
    p = _program()
    assert program_health_evidence(p, now=NOW) == []


def test_evidence_single_blocked_work_item() -> None:
    p = _program(work_items=[_wi(status="blocked")])
    ev = program_health_evidence(p, now=NOW)
    assert "1 blocked work item" in ev


def test_evidence_plural_blocked_work_items() -> None:
    p = _program(work_items=[_wi(status="blocked"), _wi(status="blocked")])
    ev = program_health_evidence(p, now=NOW)
    assert "2 blocked work items" in ev


def test_evidence_overdue_work_items() -> None:
    p = _program(work_items=[_wi(due_date=TODAY - timedelta(days=1))])
    ev = program_health_evidence(p, now=NOW)
    assert "1 overdue work item" in ev


def test_evidence_stale_work_items() -> None:
    p = _program(work_items=[_wi(updated_at=STALE_WI)])
    ev = program_health_evidence(p, now=NOW)
    assert "1 stale work item" in ev


def test_evidence_blocked_dependencies() -> None:
    p = _program(dependencies=[_dep(status="blocked")])
    ev = program_health_evidence(p, now=NOW)
    assert "1 blocked dependency" in ev


def test_evidence_critical_dependencies() -> None:
    p = _program(dependencies=[_dep(blocking_level="critical")])
    ev = program_health_evidence(p, now=NOW)
    assert "1 critical dependency" in ev


def test_evidence_excludes_resolved_critical_dep() -> None:
    p = _program(dependencies=[_dep(blocking_level="critical", status="resolved")])
    ev = program_health_evidence(p, now=NOW)
    assert not any("critical dependency" in e for e in ev)


def test_evidence_stale_dependencies() -> None:
    p = _program(dependencies=[_dep(last_confirmation_at=STALE_DEP)])
    ev = program_health_evidence(p, now=NOW)
    assert "1 stale dependency" in ev


def test_evidence_critical_risks() -> None:
    p = _program(risks=[_risk(severity="high")])
    ev = program_health_evidence(p, now=NOW)
    assert "1 critical risk" in ev


def test_evidence_stale_risks() -> None:
    p = _program(risks=[_risk(last_reviewed_at=STALE_RISK)])
    ev = program_health_evidence(p, now=NOW)
    assert "1 stale risk" in ev


def test_evidence_multiple_categories() -> None:
    p = _program(
        work_items=[_wi(status="blocked")],
        dependencies=[_dep(status="blocked")],
        risks=[_risk(severity="critical")],
    )
    ev = program_health_evidence(p, now=NOW)
    assert len(ev) == 3


def test_evidence_inactive_program_has_no_evidence() -> None:
    p = _program(work_items=[_wi(status="blocked")], is_operational=False)
    ev = program_health_evidence(p, now=NOW)
    # evidence still computes regardless of operational state
    assert "1 blocked work item" in ev


# ── UI: health pill on program list ──────────────────────────────────────────

def test_program_list_shows_health_column(client) -> None:
    client.post("/programs", json={"name": "Health Test"})
    response = client.get("/")
    assert response.status_code == 200
    assert "Health" in response.text


def test_program_list_shows_on_track_for_clean_program(client) -> None:
    client.post("/programs", json={"name": "Clean Program"})
    response = client.get("/")
    assert "On Track" in response.text


def test_program_list_shows_needs_attention_for_blocked_work_item(client) -> None:
    program = client.post("/programs", json={"name": "Needs Work"}).json()
    client.post(f"/programs/{program['id']}/work-items", json={"title": "Blocked", "status": "blocked"})
    response = client.get("/")
    assert "Needs Attention" in response.text


def test_program_detail_shows_health_and_evidence(client) -> None:
    program = client.post("/programs", json={"name": "Detail Health"}).json()
    client.post(f"/programs/{program['id']}/work-items", json={"title": "Blocked", "status": "blocked"})
    response = client.get(f"/programs/{program['id']}/view")
    assert response.status_code == 200
    assert "Health" in response.text
    assert "Needs Attention" in response.text
    assert "blocked work item" in response.text


def test_program_detail_shows_on_track_with_no_evidence(client) -> None:
    program = client.post("/programs", json={"name": "Clean Detail"}).json()
    response = client.get(f"/programs/{program['id']}/view")
    assert response.status_code == 200
    assert "On Track" in response.text


def test_program_list_filters_by_health(client) -> None:
    p1 = client.post("/programs", json={"name": "Blocked Program"}).json()
    client.post(f"/programs/{p1['id']}/work-items", json={"title": "Blocked", "status": "blocked"})
    client.post("/programs", json={"name": "Clean Program"})

    response = client.get("/?health_filter=needs_attention")

    assert response.status_code == 200
    assert "Blocked Program" in response.text
    assert "Clean Program" not in response.text


def test_morning_view_shows_health_sections(client) -> None:
    response = client.get("/morning")
    assert response.status_code == 200
    assert "Programs Off Track" in response.text
    assert "Programs At Risk" in response.text
    assert "Programs Needing Attention" in response.text


def test_morning_view_shows_program_in_correct_health_section(client) -> None:
    program = client.post("/programs", json={"name": "Trouble Program"}).json()
    client.post(f"/programs/{program['id']}/work-items", json={"title": "Blocked", "status": "blocked"})

    response = client.get("/morning")

    assert "Trouble Program" in response.text
    assert "blocked work item" in response.text
