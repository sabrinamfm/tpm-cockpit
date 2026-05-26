from datetime import date, datetime, timezone
from typing import Optional, Protocol

from app.domain.attention import (
    ProgramStatusLike,
    RiskLike,
    WorkItemLike,
    dependency_is_stale,
    risk_is_critical,
    risk_is_stale,
    work_item_is_overdue,
    work_item_is_stale,
)

HEALTH_INACTIVE = "inactive"
HEALTH_ON_TRACK = "on_track"
HEALTH_NEEDS_ATTENTION = "needs_attention"
HEALTH_AT_RISK = "at_risk"
HEALTH_OFF_TRACK = "off_track"


class HealthDependencyLike(Protocol):
    status: str
    blocking_level: str
    due_date: Optional[date]
    last_confirmation_at: Optional[datetime]


class HealthProgramLike(Protocol):
    work_items: list[WorkItemLike]
    dependencies: list[HealthDependencyLike]
    risks: list[RiskLike]
    program_status: ProgramStatusLike


def _n(count: int, singular: str, plural: str) -> str:
    return f"{count} {singular if count == 1 else plural}"


def program_health_evidence(
    program: HealthProgramLike, now: Optional[datetime] = None
) -> list[str]:
    now = now or datetime.now(timezone.utc)
    today = now.date()
    evidence = []

    blocked_wi = [w for w in program.work_items if w.status == "blocked"]
    if blocked_wi:
        evidence.append(_n(len(blocked_wi), "blocked work item", "blocked work items"))

    overdue_wi = [w for w in program.work_items if work_item_is_overdue(w, today=today)]
    if overdue_wi:
        evidence.append(_n(len(overdue_wi), "overdue work item", "overdue work items"))

    stale_wi = [w for w in program.work_items if work_item_is_stale(w, now=now)]
    if stale_wi:
        evidence.append(_n(len(stale_wi), "stale work item", "stale work items"))

    blocked_deps = [d for d in program.dependencies if d.status == "blocked"]
    if blocked_deps:
        evidence.append(_n(len(blocked_deps), "blocked dependency", "blocked dependencies"))

    critical_deps = [
        d for d in program.dependencies
        if d.blocking_level == "critical" and d.status not in ("resolved", "cancelled")
    ]
    if critical_deps:
        evidence.append(_n(len(critical_deps), "critical dependency", "critical dependencies"))

    stale_deps = [d for d in program.dependencies if dependency_is_stale(d, now=now)]
    if stale_deps:
        evidence.append(_n(len(stale_deps), "stale dependency", "stale dependencies"))

    critical_risks = [r for r in program.risks if risk_is_critical(r)]
    if critical_risks:
        evidence.append(_n(len(critical_risks), "critical risk", "critical risks"))

    stale_risks = [r for r in program.risks if risk_is_stale(r, now=now)]
    if stale_risks:
        evidence.append(_n(len(stale_risks), "stale risk", "stale risks"))

    return evidence


def program_health_state(
    program: HealthProgramLike, now: Optional[datetime] = None
) -> str:
    if not program.program_status.is_operational:
        return HEALTH_INACTIVE

    now = now or datetime.now(timezone.utc)
    today = now.date()

    has_blocked_wi = any(w.status == "blocked" for w in program.work_items)
    has_overdue_wi = any(work_item_is_overdue(w, today=today) for w in program.work_items)
    has_stale_wi = any(work_item_is_stale(w, now=now) for w in program.work_items)
    has_blocked_dep = any(d.status == "blocked" for d in program.dependencies)
    has_critical_dep = any(
        d.blocking_level == "critical" and d.status not in ("resolved", "cancelled")
        for d in program.dependencies
    )
    has_overdue_critical_dep = any(
        d.blocking_level == "critical"
        and d.status not in ("resolved", "cancelled")
        and d.due_date is not None
        and d.due_date < today
        for d in program.dependencies
    )
    has_stale_dep = any(dependency_is_stale(d, now=now) for d in program.dependencies)
    has_critical_risk = any(risk_is_critical(r) for r in program.risks)
    has_stale_risk = any(risk_is_stale(r, now=now) for r in program.risks)

    # off_track: overdue critical dep; or critical risk + blocked dep;
    # or ≥2 of {critical_dep, critical_risk, blocked_dep}
    if has_overdue_critical_dep:
        return HEALTH_OFF_TRACK
    if has_critical_risk and has_blocked_dep:
        return HEALTH_OFF_TRACK
    if sum([has_critical_dep, has_critical_risk, has_blocked_dep]) >= 2:
        return HEALTH_OFF_TRACK

    # at_risk: any critical dep or risk; or ≥3 distinct attention signals
    if has_critical_dep or has_critical_risk:
        return HEALTH_AT_RISK
    attention_signal_count = sum([
        has_blocked_wi, has_overdue_wi, has_stale_wi,
        has_blocked_dep, has_stale_dep, has_stale_risk,
    ])
    if attention_signal_count >= 3:
        return HEALTH_AT_RISK

    # needs_attention: any single moderate signal
    if any([has_blocked_wi, has_overdue_wi, has_stale_wi,
            has_blocked_dep, has_stale_dep, has_stale_risk]):
        return HEALTH_NEEDS_ATTENTION

    return HEALTH_ON_TRACK
