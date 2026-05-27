from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.domain.attention import dependency_is_stale, risk_is_critical, risk_is_stale, work_item_is_overdue, work_item_is_stale
from app.domain.health import compute_suggested_health, program_health_evidence, program_health_state
from app.domain.queries import (
    get_blocked_dependencies,
    get_blocked_work_items,
    get_critical_dependencies,
    get_critical_risks,
    get_overdue_work_items,
    get_programs_by_health,
    get_recently_updated_programs,
    get_stale_dependencies,
    get_stale_risks,
    get_stale_work_items,
)
from app.models import Decision, Dependency, Feature, Milestone, Program, ProgramStatus, Relationship, Requirement, Risk, SourceType, StatusReport, WorkItem
from app.models.program_status import seed_default_program_statuses
from app.schemas.program_status import ProgramStatusCreate, ProgramStatusUpdate

router = APIRouter(tags=["ui"])
WORK_ITEM_STATUSES = ("open", "in_progress", "blocked", "completed", "cancelled")
WORK_ITEM_PRIORITIES = ("low", "medium", "high", "critical")
WORK_ITEM_PRIORITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}
DEPENDENCY_TYPES = (
    "team",
    "approval",
    "infrastructure",
    "release",
    "vendor",
    "legal",
    "finance",
    "security",
    "product",
    "technical",
    "operational",
)
DEPENDENCY_STATUSES = ("open", "in_progress", "confirmed", "blocked", "resolved", "cancelled")
BLOCKING_LEVELS = ("low", "medium", "high", "critical")
BLOCKING_LEVEL_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}
HEALTH_STATES = ("off_track", "at_risk", "needs_attention", "on_track", "inactive")
STATUS_REPORT_HEALTHS = ("on_track", "at_risk", "off_track")
HEALTH_STATE_CSS = {
    "off_track": "off-track",
    "at_risk": "at-risk",
    "needs_attention": "attention",
    "on_track": "ok",
    "inactive": "",
}
RISK_STATUSES = ("open", "monitoring", "mitigated", "resolved", "accepted")
RISK_SEVERITIES = ("low", "medium", "high", "critical")
RISK_LIKELIHOODS = ("unlikely", "possible", "likely", "very_likely")
RISK_SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}
RISK_LIKELIHOOD_RANK = {"very_likely": 0, "likely": 1, "possible": 2, "unlikely": 3}
RISK_SORT_LABELS = {
    "severity": "Severity",
    "likelihood": "Likelihood",
    "target_resolution_date": "Target Resolution",
    "last_reviewed_at": "Last Reviewed",
    "updated_at": "Updated",
}
MILESTONE_STATUSES = ("planned", "on_track", "at_risk", "off_track", "blocked", "achieved", "cancelled")
MILESTONE_STATUS_RANK = {
    "blocked": 0, "off_track": 1, "at_risk": 2, "on_track": 3,
    "planned": 4, "achieved": 5, "cancelled": 6,
}
MILESTONE_SORT_LABELS = {
    "target_date": "Target Date",
    "status": "Status",
    "updated_at": "Updated",
}
DECISION_STATUSES = ("proposed", "decided", "deferred", "superseded", "cancelled")
DECISION_STATUS_RANK = {
    "proposed": 0, "deferred": 1, "decided": 2, "superseded": 3, "cancelled": 4,
}
DECISION_SORT_LABELS = {
    "decision_date": "Decision Date",
    "status": "Status",
    "updated_at": "Updated",
}
REQUIREMENT_SOURCE_TYPES = (
    "okr",
    "change_management",
    "customer_commitment",
    "compliance",
    "leadership_request",
    "strategic_initiative",
    "operational_requirement",
    "other",
)
REQUIREMENT_STATUSES = ("proposed", "accepted", "in_progress", "delivered", "deferred", "cancelled")
REQUIREMENT_STATUS_RANK = {
    "proposed": 0, "in_progress": 1, "accepted": 2,
    "deferred": 3, "delivered": 4, "cancelled": 5,
}
REQUIREMENT_SORT_LABELS = {
    "target_date": "Target Date",
    "source_type": "Source Type",
    "status": "Status",
}
FEATURE_STATUSES = ("proposed", "planned", "in_progress", "blocked", "delivered", "deferred", "cancelled")
FEATURE_STATUS_RANK = {
    "blocked": 0, "in_progress": 1, "proposed": 2, "planned": 3,
    "deferred": 4, "delivered": 5, "cancelled": 6,
}
FEATURE_SORT_LABELS = {
    "target_date": "Target Date",
    "status": "Status",
    "owner": "Owner",
}
RELATIONSHIP_TYPES = (
    "relates_to",
    "blocks",
    "blocked_by",
    "mitigates",
    "tracks",
    "highlights",
    "duplicates",
    "depends_on",
)
_RELATIONSHIP_OBJECT_MODEL_MAP = {
    "work_item": WorkItem,
    "dependency": Dependency,
    "risk": Risk,
    "status_report": StatusReport,
    "milestone": Milestone,
    "decision": Decision,
    "requirement": Requirement,
    "feature": Feature,
}
PROGRAM_SORTS = {
    "name": Program.name.asc(),
    "updated_at": Program.updated_at.desc(),
}
WORK_ITEM_SORT_LABELS = {
    "title": "Title",
    "status": "Status",
    "priority": "Priority",
    "owner": "Owner",
    "source_type": "Source Type",
    "due_date": "Due Date",
    "updated_at": "Updated",
    "last_touched_at": "Last Touched",
}
DEPENDENCY_SORT_LABELS = {
    "due_date": "Due Date",
    "updated_at": "Updated",
    "last_confirmation_at": "Last Confirmation",
    "blocking_level": "Blocking Level",
}

_TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"
templates = Jinja2Templates(directory=_TEMPLATES_DIR)
templates.env.globals.update(
    {
        "program_health_state": program_health_state,
        "program_health_evidence": program_health_evidence,
        "work_item_is_overdue": work_item_is_overdue,
        "work_item_is_stale": work_item_is_stale,
        "dependency_is_stale": dependency_is_stale,
        "risk_is_stale": risk_is_stale,
        "risk_is_critical": risk_is_critical,
        "WORK_ITEM_STATUSES": WORK_ITEM_STATUSES,
        "WORK_ITEM_PRIORITIES": WORK_ITEM_PRIORITIES,
        "DEPENDENCY_TYPES": DEPENDENCY_TYPES,
        "DEPENDENCY_STATUSES": DEPENDENCY_STATUSES,
        "BLOCKING_LEVELS": BLOCKING_LEVELS,
        "RISK_STATUSES": RISK_STATUSES,
        "RISK_SEVERITIES": RISK_SEVERITIES,
        "RISK_LIKELIHOODS": RISK_LIKELIHOODS,
        "WORK_ITEM_SORT_LABELS": WORK_ITEM_SORT_LABELS,
        "DEPENDENCY_SORT_LABELS": DEPENDENCY_SORT_LABELS,
        "RISK_SORT_LABELS": RISK_SORT_LABELS,
        "HEALTH_STATES": HEALTH_STATES,
        "HEALTH_STATE_CSS": HEALTH_STATE_CSS,
        "STATUS_REPORT_HEALTHS": STATUS_REPORT_HEALTHS,
        "RELATIONSHIP_TYPES": RELATIONSHIP_TYPES,
        "MILESTONE_STATUSES": MILESTONE_STATUSES,
        "MILESTONE_SORT_LABELS": MILESTONE_SORT_LABELS,
        "DECISION_STATUSES": DECISION_STATUSES,
        "DECISION_SORT_LABELS": DECISION_SORT_LABELS,
        "REQUIREMENT_SOURCE_TYPES": REQUIREMENT_SOURCE_TYPES,
        "REQUIREMENT_STATUSES": REQUIREMENT_STATUSES,
        "REQUIREMENT_SORT_LABELS": REQUIREMENT_SORT_LABELS,
        "FEATURE_STATUSES": FEATURE_STATUSES,
        "FEATURE_SORT_LABELS": FEATURE_SORT_LABELS,
    }
)
templates.env.filters.update(
    {
        "format_datetime": lambda v: v.strftime("%Y-%m-%d %H:%M") if v else "",
        "format_date": lambda v: v.isoformat() if v else "",
    }
)


def _format_date(value) -> str:
    return value.isoformat() if value else ""


async def _parse_form(request: Request) -> dict[str, str]:
    form_data = await request.body()
    parsed = parse_qs(form_data.decode())
    return {key: values[0] for key, values in parsed.items()}


def _query_string(**params: str) -> str:
    clean_params = {key: value for key, value in params.items() if value}
    return f"?{urlencode(clean_params)}" if clean_params else ""


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def program_ui(
    request: Request,
    status_filter: Optional[str] = None,
    health_filter: Optional[str] = None,
    sort: str = "updated_at",
    db: Session = Depends(get_db),
) -> HTMLResponse:
    seed_default_program_statuses(db)

    all_statuses = list(
        db.scalars(select(ProgramStatus).order_by(ProgramStatus.sort_order.asc(), ProgramStatus.id.asc()))
    )
    active_slugs = {ps.slug for ps in all_statuses if ps.is_active}

    if status_filter and status_filter not in active_slugs:
        status_filter = None
    if health_filter and health_filter not in HEALTH_STATES:
        health_filter = None
    if sort not in PROGRAM_SORTS and sort != "status":
        sort = "updated_at"

    statement = select(Program).options(
        selectinload(Program.work_items),
        selectinload(Program.dependencies),
        selectinload(Program.risks),
    )
    if status_filter:
        statement = statement.join(Program.program_status).where(ProgramStatus.slug == status_filter)
    if sort == "status":
        if not status_filter:
            statement = statement.join(Program.program_status)
        statement = statement.order_by(ProgramStatus.sort_order.asc(), Program.id.desc())
    else:
        statement = statement.order_by(PROGRAM_SORTS[sort], Program.id.desc())
    programs = list(db.scalars(statement))
    if health_filter:
        programs = [p for p in programs if program_health_state(p) == health_filter]

    program_ids = [p.id for p in programs]
    latest_reports: dict[int, StatusReport] = {}
    if program_ids:
        for report in db.scalars(
            select(StatusReport)
            .where(StatusReport.program_id.in_(program_ids))
            .order_by(StatusReport.report_date.desc(), StatusReport.created_at.desc())
        ):
            if report.program_id not in latest_reports:
                latest_reports[report.program_id] = report

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "all_statuses": all_statuses,
            "programs": programs,
            "status_filter": status_filter,
            "health_filter": health_filter,
            "sort": sort,
            "latest_reports": latest_reports,
        },
    )


@router.post("/programs/create", include_in_schema=False)
async def create_program_from_ui(request: Request, db: Session = Depends(get_db)) -> RedirectResponse:
    parsed = await _parse_form(request)
    name = parsed.get("name", "").strip()
    description = parsed.get("description", "").strip() or None
    slug = parsed.get("status", "active")
    if not name:
        return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    ps = db.scalar(select(ProgramStatus).where(ProgramStatus.slug == slug, ProgramStatus.is_active.is_(True)))
    if ps is None:
        ps = db.scalar(select(ProgramStatus).where(ProgramStatus.is_default.is_(True)))
    if ps is None:
        ps = db.scalar(select(ProgramStatus).order_by(ProgramStatus.sort_order.asc()))
    if ps is None:
        return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    db.add(Program(
        name=name,
        description=description,
        launch_date=_parse_due_date(parsed.get("launch_date", "")),
        status_id=ps.id,
    ))
    db.commit()
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/programs/{program_id}/edit", response_class=HTMLResponse, include_in_schema=False)
def edit_program_page(request: Request, program_id: int, db: Session = Depends(get_db)) -> HTMLResponse:
    program = db.get(Program, program_id)
    if program is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")
    all_statuses = list(
        db.scalars(select(ProgramStatus).order_by(ProgramStatus.sort_order.asc(), ProgramStatus.id.asc()))
    )
    return templates.TemplateResponse(
        request, "edit_program.html", {"program": program, "all_statuses": all_statuses}
    )


@router.post("/programs/{program_id}/update", include_in_schema=False)
async def update_program_from_ui(
    program_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    program = db.get(Program, program_id)
    if program is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")
    parsed = await _parse_form(request)
    name = parsed.get("name", "").strip()
    slug = parsed.get("status", program.status)
    ps = db.scalar(select(ProgramStatus).where(ProgramStatus.slug == slug))
    if name and ps is not None:
        program.name = name
        program.description = parsed.get("description", "").strip() or None
        program.launch_date = _parse_due_date(parsed.get("launch_date", ""))
        program.status_id = ps.id
        db.add(program)
        db.commit()
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/programs/{program_id}/delete/confirm", response_class=HTMLResponse, include_in_schema=False)
def confirm_delete_program_page(request: Request, program_id: int, db: Session = Depends(get_db)) -> HTMLResponse:
    program = db.get(Program, program_id)
    if program is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")
    return templates.TemplateResponse(
        request,
        "confirm_delete.html",
        {
            "page_title": "Delete Program?",
            "subtitle": program.name,
            "back_url": "/",
            "back_label": "Back to Programs",
            "message": "Deleting this Program will also delete its Work Items.",
            "action_url": f"/programs/{program.id}/delete",
            "cancel_url": "/",
        },
    )


@router.post("/programs/{program_id}/delete", include_in_schema=False)
def delete_program_from_ui(program_id: int, db: Session = Depends(get_db)) -> RedirectResponse:
    program = db.get(Program, program_id)
    if program is not None:
        db.delete(program)
        db.commit()
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)


def _parse_due_date(value: str) -> Optional[date]:
    if not value:
        return None
    return date.fromisoformat(value)


def _parse_optional_datetime(value: str) -> Optional[datetime]:
    if not value:
        return None
    return datetime.fromisoformat(value)


def _parse_optional_int(value: str) -> Optional[int]:
    if not value:
        return None
    return int(value)


def _work_item_sort_key(work_item: WorkItem, sort: str):
    if sort == "title":
        return (work_item.title.lower(), work_item.id)
    if sort == "status":
        return (work_item.status, work_item.id)
    if sort == "priority":
        return (WORK_ITEM_PRIORITY_RANK.get(work_item.priority, 99), work_item.id)
    if sort == "owner":
        return ((work_item.owner or "").lower(), work_item.id)
    if sort == "source_type":
        return ((work_item.source_type.name if work_item.source_type else "").lower(), work_item.id)
    if sort == "due_date":
        return (work_item.due_date or date.max, work_item.id)
    if sort == "last_touched_at":
        return (work_item.last_touched_at or datetime.min, work_item.id)
    return (work_item.updated_at, work_item.id)


def _dependency_sort_key(dependency: Dependency, sort: str):
    if sort == "due_date":
        return (dependency.due_date or date.max, dependency.id)
    if sort == "last_confirmation_at":
        return (dependency.last_confirmation_at or datetime.min, dependency.id)
    if sort == "blocking_level":
        return (BLOCKING_LEVEL_RANK.get(dependency.blocking_level, 99), dependency.id)
    return (dependency.updated_at, dependency.id)


def _risk_sort_key(risk: Risk, sort: str):
    if sort == "severity":
        return (RISK_SEVERITY_RANK.get(risk.severity, 99), risk.id)
    if sort == "likelihood":
        return (RISK_LIKELIHOOD_RANK.get(risk.likelihood, 99), risk.id)
    if sort == "target_resolution_date":
        return (risk.target_resolution_date or date.max, risk.id)
    if sort == "last_reviewed_at":
        return (risk.last_reviewed_at or datetime.min, risk.id)
    return (risk.updated_at, risk.id)


def _feature_sort_key(feature: Feature, sort: str):
    if sort == "target_date":
        return (feature.target_date or date.max, feature.id)
    if sort == "status":
        return (FEATURE_STATUS_RANK.get(feature.status, 99), feature.id)
    if sort == "owner":
        return (feature.owner or "", feature.id)
    return (feature.target_date or date.max, feature.id)


def _requirement_sort_key(req: Requirement, sort: str):
    if sort == "target_date":
        return (req.target_date or date.max, req.id)
    if sort == "source_type":
        return (req.source_type, req.id)
    if sort == "status":
        return (REQUIREMENT_STATUS_RANK.get(req.status, 99), req.id)
    return (req.target_date or date.max, req.id)


def _decision_sort_key(decision: Decision, sort: str):
    if sort == "decision_date":
        return (decision.decision_date or date.max, decision.id)
    if sort == "status":
        return (DECISION_STATUS_RANK.get(decision.status, 99), decision.id)
    return (decision.updated_at, decision.id)


def _milestone_sort_key(milestone: Milestone, sort: str):
    if sort == "target_date":
        return (milestone.target_date or date.max, milestone.id)
    if sort == "status":
        return (MILESTONE_STATUS_RANK.get(milestone.status, 99), milestone.id)
    return (milestone.updated_at, milestone.id)


@router.get("/programs/{program_id}/view", response_class=HTMLResponse, include_in_schema=False)
def program_detail(
    request: Request,
    program_id: int,
    work_status_filter: Optional[str] = None,
    priority_filter: Optional[str] = None,
    stale_filter: Optional[str] = None,
    owner_filter: Optional[str] = None,
    source_type_filter: Optional[str] = None,
    work_sort: str = "updated_at",
    show_new_work_item: Optional[str] = None,
    work_item_error: Optional[str] = None,
    edit_work_item_id: Optional[int] = None,
    dependency_status_filter: Optional[str] = None,
    dependency_type_filter: Optional[str] = None,
    blocking_level_filter: Optional[str] = None,
    dependency_owner_filter: Optional[str] = None,
    dependency_sort: str = "updated_at",
    show_new_dependency: Optional[str] = None,
    dependency_error: Optional[str] = None,
    edit_dependency_id: Optional[int] = None,
    risk_status_filter: Optional[str] = None,
    risk_severity_filter: Optional[str] = None,
    risk_likelihood_filter: Optional[str] = None,
    risk_owner_filter: Optional[str] = None,
    risk_sort: str = "updated_at",
    show_new_risk: Optional[str] = None,
    risk_error: Optional[str] = None,
    edit_risk_id: Optional[int] = None,
    show_new_report: Optional[str] = None,
    report_error: Optional[str] = None,
    edit_report_id: Optional[int] = None,
    milestone_sort: str = "target_date",
    show_new_milestone: Optional[str] = None,
    milestone_error: Optional[str] = None,
    edit_milestone_id: Optional[int] = None,
    decision_sort: str = "decision_date",
    show_new_decision: Optional[str] = None,
    decision_error: Optional[str] = None,
    edit_decision_id: Optional[int] = None,
    req_source_type_filter: Optional[str] = None,
    req_status_filter: Optional[str] = None,
    req_owner_filter: Optional[str] = None,
    requirement_sort: str = "target_date",
    show_new_requirement: Optional[str] = None,
    requirement_error: Optional[str] = None,
    edit_requirement_id: Optional[int] = None,
    feature_status_filter: Optional[str] = None,
    feature_owner_filter: Optional[str] = None,
    feature_sort: str = "target_date",
    show_new_feature: Optional[str] = None,
    feature_error: Optional[str] = None,
    edit_feature_id: Optional[int] = None,
    show_new_relationship: Optional[str] = None,
    relationship_error: Optional[str] = None,
    return_to: str = "",
    db: Session = Depends(get_db),
) -> HTMLResponse:
    program = db.scalars(
        select(Program)
        .options(
            selectinload(Program.work_items).selectinload(WorkItem.source_type),
            selectinload(Program.dependencies),
            selectinload(Program.risks),
            selectinload(Program.status_reports),
            selectinload(Program.milestones),
            selectinload(Program.decisions),
            selectinload(Program.requirements),
            selectinload(Program.features),
        )
        .where(Program.id == program_id)
    ).one_or_none()
    if program is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")
    health = program_health_state(program)
    health_evidence = program_health_evidence(program)
    source_types = list(db.scalars(select(SourceType).order_by(SourceType.name.asc())))

    if work_status_filter and work_status_filter not in WORK_ITEM_STATUSES:
        work_status_filter = None
    if priority_filter and priority_filter not in WORK_ITEM_PRIORITIES:
        priority_filter = None
    if stale_filter and stale_filter not in ("stale", "not_stale"):
        stale_filter = None
    if work_sort not in WORK_ITEM_SORT_LABELS:
        work_sort = "updated_at"
    if dependency_status_filter and dependency_status_filter not in DEPENDENCY_STATUSES:
        dependency_status_filter = None
    if dependency_type_filter and dependency_type_filter not in DEPENDENCY_TYPES:
        dependency_type_filter = None
    if blocking_level_filter and blocking_level_filter not in BLOCKING_LEVELS:
        blocking_level_filter = None
    if dependency_sort not in DEPENDENCY_SORT_LABELS:
        dependency_sort = "updated_at"
    if risk_status_filter and risk_status_filter not in RISK_STATUSES:
        risk_status_filter = None
    if risk_severity_filter and risk_severity_filter not in RISK_SEVERITIES:
        risk_severity_filter = None
    if risk_likelihood_filter and risk_likelihood_filter not in RISK_LIKELIHOODS:
        risk_likelihood_filter = None
    if risk_sort not in RISK_SORT_LABELS:
        risk_sort = "updated_at"
    if milestone_sort not in MILESTONE_SORT_LABELS:
        milestone_sort = "target_date"
    if decision_sort not in DECISION_SORT_LABELS:
        decision_sort = "decision_date"
    if req_source_type_filter and req_source_type_filter not in REQUIREMENT_SOURCE_TYPES:
        req_source_type_filter = None
    if req_status_filter and req_status_filter not in REQUIREMENT_STATUSES:
        req_status_filter = None
    if requirement_sort not in REQUIREMENT_SORT_LABELS:
        requirement_sort = "target_date"
    if feature_status_filter and feature_status_filter not in FEATURE_STATUSES:
        feature_status_filter = None
    if feature_sort not in FEATURE_SORT_LABELS:
        feature_sort = "target_date"

    work_items = list(program.work_items)
    if work_status_filter:
        work_items = [item for item in work_items if item.status == work_status_filter]
    if priority_filter:
        work_items = [item for item in work_items if item.priority == priority_filter]
    if stale_filter == "stale":
        work_items = [item for item in work_items if work_item_is_stale(item)]
    elif stale_filter == "not_stale":
        work_items = [item for item in work_items if not work_item_is_stale(item)]
    if owner_filter:
        work_items = [item for item in work_items if item.owner == owner_filter]
    if source_type_filter:
        source_type_id = int(source_type_filter)
        work_items = [item for item in work_items if item.source_type_id == source_type_id]
    reverse = work_sort == "updated_at"
    work_items = sorted(work_items, key=lambda item: _work_item_sort_key(item, work_sort), reverse=reverse)

    dependencies = list(program.dependencies)
    if dependency_status_filter:
        dependencies = [item for item in dependencies if item.status == dependency_status_filter]
    if dependency_type_filter:
        dependencies = [item for item in dependencies if item.dependency_type == dependency_type_filter]
    if blocking_level_filter:
        dependencies = [item for item in dependencies if item.blocking_level == blocking_level_filter]
    if dependency_owner_filter:
        dependencies = [item for item in dependencies if item.owner == dependency_owner_filter]
    dependency_reverse = dependency_sort in ("updated_at", "last_confirmation_at")
    dependencies = sorted(
        dependencies,
        key=lambda item: _dependency_sort_key(item, dependency_sort),
        reverse=dependency_reverse,
    )

    risks = list(program.risks)
    if risk_status_filter:
        risks = [r for r in risks if r.status == risk_status_filter]
    if risk_severity_filter:
        risks = [r for r in risks if r.severity == risk_severity_filter]
    if risk_likelihood_filter:
        risks = [r for r in risks if r.likelihood == risk_likelihood_filter]
    if risk_owner_filter:
        risks = [r for r in risks if r.owner == risk_owner_filter]
    risk_reverse = risk_sort == "updated_at"
    risks = sorted(risks, key=lambda r: _risk_sort_key(r, risk_sort), reverse=risk_reverse)

    edit_work_item = None
    if edit_work_item_id is not None:
        edit_work_item = next(
            (item for item in program.work_items if item.id == edit_work_item_id),
            None,
        )
    edit_dependency = None
    if edit_dependency_id is not None:
        edit_dependency = next(
            (item for item in program.dependencies if item.id == edit_dependency_id),
            None,
        )

    edit_risk = None
    if edit_risk_id is not None:
        edit_risk = next(
            (r for r in program.risks if r.id == edit_risk_id),
            None,
        )

    work_owners = sorted({item.owner for item in program.work_items if item.owner})
    dep_owners = sorted({item.owner for item in program.dependencies if item.owner})
    risk_owners = sorted({r.owner for r in program.risks if r.owner})

    status_reports = sorted(
        program.status_reports,
        key=lambda r: (r.report_date, r.created_at),
        reverse=True,
    )
    edit_report = None
    if edit_report_id is not None:
        edit_report = next((r for r in status_reports if r.id == edit_report_id), None)

    milestones = sorted(
        program.milestones,
        key=lambda m: _milestone_sort_key(m, milestone_sort),
        reverse=milestone_sort == "updated_at",
    )
    edit_milestone = None
    if edit_milestone_id is not None:
        edit_milestone = next((m for m in program.milestones if m.id == edit_milestone_id), None)

    decisions = sorted(
        program.decisions,
        key=lambda d: _decision_sort_key(d, decision_sort),
        reverse=decision_sort == "updated_at",
    )
    edit_decision = None
    if edit_decision_id is not None:
        edit_decision = next((d for d in program.decisions if d.id == edit_decision_id), None)

    decision_owners = sorted({d.owner for d in program.decisions if d.owner})

    requirements = list(program.requirements)
    if req_source_type_filter:
        requirements = [r for r in requirements if r.source_type == req_source_type_filter]
    if req_status_filter:
        requirements = [r for r in requirements if r.status == req_status_filter]
    if req_owner_filter:
        requirements = [r for r in requirements if r.owner == req_owner_filter]
    requirements = sorted(requirements, key=lambda r: _requirement_sort_key(r, requirement_sort))
    edit_requirement = None
    if edit_requirement_id is not None:
        edit_requirement = next((r for r in program.requirements if r.id == edit_requirement_id), None)
    req_owners = sorted({r.owner for r in program.requirements if r.owner})

    features = list(program.features)
    if feature_status_filter:
        features = [f for f in features if f.status == feature_status_filter]
    if feature_owner_filter:
        features = [f for f in features if f.owner == feature_owner_filter]
    features = sorted(features, key=lambda f: _feature_sort_key(f, feature_sort))
    edit_feature = None
    if edit_feature_id is not None:
        edit_feature = next((f for f in program.features if f.id == edit_feature_id), None)
    feature_owners = sorted({f.owner for f in program.features if f.owner})

    # Build lookup and load relationships for all objects in this program
    rel_object_lookup: dict[str, dict] = {}
    all_program_objects: list[dict] = []
    for wi in program.work_items:
        info = {"type": "work_item", "id": wi.id, "display_id": wi.display_id, "title": wi.title}
        rel_object_lookup[f"work_item:{wi.id}"] = info
        all_program_objects.append(info)
    for dep in program.dependencies:
        info = {"type": "dependency", "id": dep.id, "display_id": dep.display_id, "title": dep.title}
        rel_object_lookup[f"dependency:{dep.id}"] = info
        all_program_objects.append(info)
    for r in program.risks:
        info = {"type": "risk", "id": r.id, "display_id": r.display_id, "title": r.title}
        rel_object_lookup[f"risk:{r.id}"] = info
        all_program_objects.append(info)
    for sr in program.status_reports:
        info = {"type": "status_report", "id": sr.id, "display_id": sr.display_id, "title": str(sr.report_date)}
        rel_object_lookup[f"status_report:{sr.id}"] = info
        all_program_objects.append(info)
    for ms in program.milestones:
        info = {"type": "milestone", "id": ms.id, "display_id": ms.display_id, "title": ms.title}
        rel_object_lookup[f"milestone:{ms.id}"] = info
        all_program_objects.append(info)
    for dec in program.decisions:
        info = {"type": "decision", "id": dec.id, "display_id": dec.display_id, "title": dec.title}
        rel_object_lookup[f"decision:{dec.id}"] = info
        all_program_objects.append(info)
    for req in program.requirements:
        info = {"type": "requirement", "id": req.id, "display_id": req.display_id, "title": req.title}
        rel_object_lookup[f"requirement:{req.id}"] = info
        all_program_objects.append(info)
    for ft in program.features:
        info = {"type": "feature", "id": ft.id, "display_id": ft.display_id, "title": ft.title}
        rel_object_lookup[f"feature:{ft.id}"] = info
        all_program_objects.append(info)

    rel_conditions = []
    for type_name, ids in [
        ("work_item", [wi.id for wi in program.work_items]),
        ("dependency", [dep.id for dep in program.dependencies]),
        ("risk", [r.id for r in program.risks]),
        ("status_report", [sr.id for sr in program.status_reports]),
        ("milestone", [ms.id for ms in program.milestones]),
        ("decision", [dec.id for dec in program.decisions]),
        ("requirement", [req.id for req in program.requirements]),
        ("feature", [ft.id for ft in program.features]),
    ]:
        if ids:
            rel_conditions.extend([
                (Relationship.source_type == type_name) & (Relationship.source_id.in_(ids)),
                (Relationship.target_type == type_name) & (Relationship.target_id.in_(ids)),
            ])
    relationships = []
    if rel_conditions:
        relationships = list(
            db.scalars(
                select(Relationship)
                .where(or_(*rel_conditions))
                .order_by(Relationship.created_at.desc())
            )
        )

    return templates.TemplateResponse(
        request,
        "program_detail.html",
        {
            "program": program,
            "health": health,
            "health_evidence": health_evidence,
            "source_types": source_types,
            "work_items": work_items,
            "work_status_filter": work_status_filter,
            "priority_filter": priority_filter,
            "stale_filter": stale_filter,
            "owner_filter": owner_filter,
            "source_type_filter": source_type_filter,
            "work_sort": work_sort,
            "show_new_work_item": show_new_work_item,
            "work_item_error": work_item_error,
            "edit_work_item": edit_work_item,
            "work_owners": work_owners,
            "dependencies": dependencies,
            "dependency_status_filter": dependency_status_filter,
            "dependency_type_filter": dependency_type_filter,
            "blocking_level_filter": blocking_level_filter,
            "dependency_owner_filter": dependency_owner_filter,
            "dependency_sort": dependency_sort,
            "show_new_dependency": show_new_dependency,
            "dependency_error": dependency_error,
            "edit_dependency": edit_dependency,
            "dep_owners": dep_owners,
            "risks": risks,
            "risk_status_filter": risk_status_filter,
            "risk_severity_filter": risk_severity_filter,
            "risk_likelihood_filter": risk_likelihood_filter,
            "risk_owner_filter": risk_owner_filter,
            "risk_sort": risk_sort,
            "show_new_risk": show_new_risk,
            "risk_error": risk_error,
            "edit_risk": edit_risk,
            "risk_owners": risk_owners,
            "status_reports": status_reports,
            "show_new_report": show_new_report,
            "report_error": report_error,
            "edit_report": edit_report,
            "milestones": milestones,
            "milestone_sort": milestone_sort,
            "show_new_milestone": show_new_milestone,
            "milestone_error": milestone_error,
            "edit_milestone": edit_milestone,
            "decisions": decisions,
            "decision_sort": decision_sort,
            "show_new_decision": show_new_decision,
            "decision_error": decision_error,
            "edit_decision": edit_decision,
            "decision_owners": decision_owners,
            "requirements": requirements,
            "req_source_type_filter": req_source_type_filter,
            "req_status_filter": req_status_filter,
            "req_owner_filter": req_owner_filter,
            "requirement_sort": requirement_sort,
            "show_new_requirement": show_new_requirement,
            "requirement_error": requirement_error,
            "edit_requirement": edit_requirement,
            "req_owners": req_owners,
            "features": features,
            "feature_status_filter": feature_status_filter,
            "feature_owner_filter": feature_owner_filter,
            "feature_sort": feature_sort,
            "show_new_feature": show_new_feature,
            "feature_error": feature_error,
            "edit_feature": edit_feature,
            "feature_owners": feature_owners,
            "relationships": relationships,
            "rel_object_lookup": rel_object_lookup,
            "all_program_objects": all_program_objects,
            "show_new_relationship": show_new_relationship,
            "relationship_error": relationship_error,
            "return_to": return_to,
            "today": date.today(),
        },
    )


@router.post("/programs/{program_id}/work-items/create", include_in_schema=False)
async def create_work_item_from_ui(
    program_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    if db.get(Program, program_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")

    parsed = await _parse_form(request)
    title = parsed.get("title", "").strip()
    work_status = parsed.get("status", "open")
    source_type_id = _parse_optional_int(parsed.get("source_type_id", ""))
    if source_type_id is not None and db.get(SourceType, source_type_id) is None:
        source_type_id = None
    if not title or work_status not in WORK_ITEM_STATUSES:
        query = urlencode(
            {
                "show_new_work_item": "1",
                "work_item_error": "Title and status are required.",
            }
        )
        return RedirectResponse(
            f"/programs/{program_id}/view?{query}#new-work-item",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    work_item = WorkItem(
        program_id=program_id,
        title=title,
        description=parsed.get("description", "").strip() or None,
        status=work_status,
        priority=parsed.get("priority", "medium") if parsed.get("priority", "medium") in WORK_ITEM_PRIORITIES else "medium",
        owner=parsed.get("owner", "").strip() or None,
        next_step=parsed.get("next_step", "").strip() or None,
        source_type_id=source_type_id,
        link=parsed.get("link", "").strip() or None,
        due_date=_parse_due_date(parsed.get("due_date", "")),
    )
    db.add(work_item)
    db.commit()
    return RedirectResponse(f"/programs/{program_id}/view", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/work-items/{work_item_id}/update", include_in_schema=False)
async def update_work_item_from_ui(
    work_item_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    work_item = db.get(WorkItem, work_item_id)
    if work_item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work item not found")

    parsed = await _parse_form(request)
    title = parsed.get("title", "").strip()
    work_status = parsed.get("status", work_item.status)
    priority = parsed.get("priority", work_item.priority)
    source_type_id = _parse_optional_int(parsed.get("source_type_id", ""))
    if source_type_id is not None and db.get(SourceType, source_type_id) is None:
        source_type_id = None
    if title and work_status in WORK_ITEM_STATUSES and priority in WORK_ITEM_PRIORITIES:
        work_item.title = title
        work_item.description = parsed.get("description", "").strip() or None
        work_item.status = work_status
        work_item.priority = priority
        work_item.owner = parsed.get("owner", "").strip() or None
        work_item.next_step = parsed.get("next_step", "").strip() or None
        work_item.source_type_id = source_type_id
        work_item.link = parsed.get("link", "").strip() or None
        work_item.due_date = _parse_due_date(parsed.get("due_date", ""))
        db.add(work_item)
        db.commit()

    return RedirectResponse(f"/programs/{work_item.program_id}/view", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/work-items/{work_item_id}/touch", include_in_schema=False)
def mark_work_item_touched_from_ui(work_item_id: int, db: Session = Depends(get_db)) -> RedirectResponse:
    work_item = db.get(WorkItem, work_item_id)
    if work_item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work item not found")

    work_item.last_touched_at = datetime.now(timezone.utc)
    db.add(work_item)
    db.commit()
    return RedirectResponse(f"/programs/{work_item.program_id}/view", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/work-items/{work_item_id}/delete/confirm", response_class=HTMLResponse, include_in_schema=False)
def confirm_delete_work_item_page(
    request: Request, work_item_id: int, db: Session = Depends(get_db)
) -> HTMLResponse:
    work_item = db.get(WorkItem, work_item_id)
    if work_item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work item not found")
    return templates.TemplateResponse(
        request,
        "confirm_delete.html",
        {
            "page_title": "Delete Work Item?",
            "subtitle": work_item.title,
            "back_url": f"/programs/{work_item.program_id}/view",
            "back_label": "Back to Program",
            "message": "This removes the Work Item from the Program.",
            "action_url": f"/work-items/{work_item.id}/delete",
            "cancel_url": f"/programs/{work_item.program_id}/view",
        },
    )


@router.post("/work-items/{work_item_id}/delete", include_in_schema=False)
def delete_work_item_from_ui(work_item_id: int, db: Session = Depends(get_db)) -> RedirectResponse:
    work_item = db.get(WorkItem, work_item_id)
    if work_item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work item not found")

    program_id = work_item.program_id
    db.delete(work_item)
    db.commit()
    return RedirectResponse(f"/programs/{program_id}/view", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/programs/{program_id}/dependencies/create", include_in_schema=False)
async def create_dependency_from_ui(
    program_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    if db.get(Program, program_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")

    parsed = await _parse_form(request)
    title = parsed.get("title", "").strip()
    dependency_type = parsed.get("dependency_type", "team")
    dependency_status = parsed.get("status", "open")
    blocking_level = parsed.get("blocking_level", "medium")
    if (
        not title
        or dependency_type not in DEPENDENCY_TYPES
        or dependency_status not in DEPENDENCY_STATUSES
        or blocking_level not in BLOCKING_LEVELS
    ):
        query = urlencode(
            {
                "show_new_dependency": "1",
                "dependency_error": "Title, type, status, and blocking level are required.",
            }
        )
        return RedirectResponse(
            f"/programs/{program_id}/view?{query}#new-dependency",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    dependency = Dependency(
        program_id=program_id,
        title=title,
        description=parsed.get("description", "").strip() or None,
        dependency_type=dependency_type,
        owner=parsed.get("owner", "").strip() or None,
        external_team=parsed.get("external_team", "").strip() or None,
        status=dependency_status,
        blocking_level=blocking_level,
        due_date=_parse_due_date(parsed.get("due_date", "")),
        last_confirmation_at=_parse_optional_datetime(parsed.get("last_confirmation_at", "")),
        notes=parsed.get("notes", "").strip() or None,
    )
    db.add(dependency)
    db.commit()
    return RedirectResponse(f"/programs/{program_id}/view", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/dependencies/{dependency_id}/update", include_in_schema=False)
async def update_dependency_from_ui(
    dependency_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    dependency = db.get(Dependency, dependency_id)
    if dependency is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dependency not found")

    parsed = await _parse_form(request)
    title = parsed.get("title", "").strip()
    dependency_type = parsed.get("dependency_type", dependency.dependency_type)
    dependency_status = parsed.get("status", dependency.status)
    blocking_level = parsed.get("blocking_level", dependency.blocking_level)
    if (
        title
        and dependency_type in DEPENDENCY_TYPES
        and dependency_status in DEPENDENCY_STATUSES
        and blocking_level in BLOCKING_LEVELS
    ):
        dependency.title = title
        dependency.description = parsed.get("description", "").strip() or None
        dependency.dependency_type = dependency_type
        dependency.owner = parsed.get("owner", "").strip() or None
        dependency.external_team = parsed.get("external_team", "").strip() or None
        dependency.status = dependency_status
        dependency.blocking_level = blocking_level
        dependency.due_date = _parse_due_date(parsed.get("due_date", ""))
        dependency.last_confirmation_at = _parse_optional_datetime(parsed.get("last_confirmation_at", ""))
        dependency.notes = parsed.get("notes", "").strip() or None
        db.add(dependency)
        db.commit()

    return_to = parsed.get("return_to", "")
    if return_to and return_to.startswith("/"):
        return RedirectResponse(return_to, status_code=status.HTTP_303_SEE_OTHER)
    return RedirectResponse(f"/programs/{dependency.program_id}/view", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/dependencies/{dependency_id}/confirm-ui", include_in_schema=False)
def confirm_dependency_from_ui(dependency_id: int, db: Session = Depends(get_db)) -> RedirectResponse:
    dependency = db.get(Dependency, dependency_id)
    if dependency is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dependency not found")

    dependency.last_confirmation_at = datetime.now(timezone.utc)
    db.add(dependency)
    db.commit()
    return RedirectResponse(f"/programs/{dependency.program_id}/view", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/dependencies/{dependency_id}/delete/confirm", response_class=HTMLResponse, include_in_schema=False)
def confirm_delete_dependency_page(
    request: Request, dependency_id: int, db: Session = Depends(get_db)
) -> HTMLResponse:
    dependency = db.get(Dependency, dependency_id)
    if dependency is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dependency not found")
    return templates.TemplateResponse(
        request,
        "confirm_delete.html",
        {
            "page_title": "Delete Dependency?",
            "subtitle": dependency.title,
            "back_url": f"/programs/{dependency.program_id}/view",
            "back_label": "Back to Program",
            "message": "This removes the Dependency from the Program.",
            "action_url": f"/dependencies/{dependency.id}/delete",
            "cancel_url": f"/programs/{dependency.program_id}/view",
        },
    )


@router.post("/dependencies/{dependency_id}/delete", include_in_schema=False)
def delete_dependency_from_ui(dependency_id: int, db: Session = Depends(get_db)) -> RedirectResponse:
    dependency = db.get(Dependency, dependency_id)
    if dependency is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dependency not found")

    program_id = dependency.program_id
    db.delete(dependency)
    db.commit()
    return RedirectResponse(f"/programs/{program_id}/view", status_code=status.HTTP_303_SEE_OTHER)


# ── Risk UI handlers ─────────────────────────────────────────────────────────

@router.post("/programs/{program_id}/risks/create", include_in_schema=False)
async def create_risk_from_ui(
    program_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    if db.get(Program, program_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")

    parsed = await _parse_form(request)
    title = parsed.get("title", "").strip()
    risk_status = parsed.get("status", "open")
    severity = parsed.get("severity", "medium")
    likelihood = parsed.get("likelihood", "possible")
    if (
        not title
        or risk_status not in RISK_STATUSES
        or severity not in RISK_SEVERITIES
        or likelihood not in RISK_LIKELIHOODS
    ):
        query = urlencode(
            {
                "show_new_risk": "1",
                "risk_error": "Title, status, severity, and likelihood are required.",
            }
        )
        return RedirectResponse(
            f"/programs/{program_id}/view?{query}#new-risk",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    risk = Risk(
        program_id=program_id,
        title=title,
        description=parsed.get("description", "").strip() or None,
        severity=severity,
        likelihood=likelihood,
        status=risk_status,
        owner=parsed.get("owner", "").strip() or None,
        mitigation=parsed.get("mitigation", "").strip() or None,
        target_resolution_date=_parse_due_date(parsed.get("target_resolution_date", "")),
    )
    db.add(risk)
    db.commit()
    return RedirectResponse(f"/programs/{program_id}/view", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/risks/{risk_id}/update", include_in_schema=False)
async def update_risk_from_ui(
    risk_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    risk = db.get(Risk, risk_id)
    if risk is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Risk not found")

    parsed = await _parse_form(request)
    title = parsed.get("title", "").strip()
    risk_status = parsed.get("status", risk.status)
    severity = parsed.get("severity", risk.severity)
    likelihood = parsed.get("likelihood", risk.likelihood)
    if (
        title
        and risk_status in RISK_STATUSES
        and severity in RISK_SEVERITIES
        and likelihood in RISK_LIKELIHOODS
    ):
        risk.title = title
        risk.description = parsed.get("description", "").strip() or None
        risk.severity = severity
        risk.likelihood = likelihood
        risk.status = risk_status
        risk.owner = parsed.get("owner", "").strip() or None
        risk.mitigation = parsed.get("mitigation", "").strip() or None
        risk.target_resolution_date = _parse_due_date(parsed.get("target_resolution_date", ""))
        db.add(risk)
        db.commit()

    return_to = parsed.get("return_to", "")
    if return_to and return_to.startswith("/"):
        return RedirectResponse(return_to, status_code=status.HTTP_303_SEE_OTHER)
    return RedirectResponse(f"/programs/{risk.program_id}/view", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/risks/{risk_id}/review-ui", include_in_schema=False)
def review_risk_from_ui(risk_id: int, db: Session = Depends(get_db)) -> RedirectResponse:
    risk = db.get(Risk, risk_id)
    if risk is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Risk not found")

    risk.last_reviewed_at = datetime.now(timezone.utc)
    db.add(risk)
    db.commit()
    return RedirectResponse(f"/programs/{risk.program_id}/view", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/risks/{risk_id}/delete/confirm", response_class=HTMLResponse, include_in_schema=False)
def confirm_delete_risk_page(
    request: Request, risk_id: int, db: Session = Depends(get_db)
) -> HTMLResponse:
    risk = db.get(Risk, risk_id)
    if risk is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Risk not found")
    return templates.TemplateResponse(
        request,
        "confirm_delete.html",
        {
            "page_title": "Delete Risk?",
            "subtitle": risk.title,
            "back_url": f"/programs/{risk.program_id}/view",
            "back_label": "Back to Program",
            "message": "This removes the Risk from the Program.",
            "action_url": f"/risks/{risk.id}/delete",
            "cancel_url": f"/programs/{risk.program_id}/view",
        },
    )


@router.post("/risks/{risk_id}/delete", include_in_schema=False)
def delete_risk_from_ui(risk_id: int, db: Session = Depends(get_db)) -> RedirectResponse:
    risk = db.get(Risk, risk_id)
    if risk is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Risk not found")

    program_id = risk.program_id
    db.delete(risk)
    db.commit()
    return RedirectResponse(f"/programs/{program_id}/view", status_code=status.HTTP_303_SEE_OTHER)


# ── Status Report UI handlers ─────────────────────────────────────────────────

@router.get("/status-reports/{report_id}/view", response_class=HTMLResponse, include_in_schema=False)
def view_status_report(
    request: Request,
    report_id: int,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    report = db.get(StatusReport, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Status report not found")

    program = db.scalars(
        select(Program)
        .options(
            selectinload(Program.work_items),
            selectinload(Program.dependencies),
            selectinload(Program.risks),
            selectinload(Program.milestones),
            selectinload(Program.requirements),
            selectinload(Program.features),
            selectinload(Program.decisions),
        )
        .where(Program.id == report.program_id)
    ).one_or_none()

    milestones_sorted = sorted(
        program.milestones,
        key=lambda ms: (ms.target_date is None, ms.target_date),
    )

    return templates.TemplateResponse(
        request,
        "status_report_detail.html",
        {
            "report": report,
            "program": program,
            "milestones_sorted": milestones_sorted,
            "HEALTH_STATE_CSS": HEALTH_STATE_CSS,
            "STATUS_REPORT_HEALTHS": STATUS_REPORT_HEALTHS,
        },
    )


@router.post("/status-reports/{report_id}/recalculate-health", include_in_schema=False)
def recalculate_status_report_health(
    report_id: int,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    report = db.get(StatusReport, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Status report not found")

    program = db.scalars(
        select(Program)
        .options(
            selectinload(Program.work_items),
            selectinload(Program.dependencies),
            selectinload(Program.risks),
        )
        .where(Program.id == report.program_id)
    ).one_or_none()

    report.suggested_health = compute_suggested_health(program)
    db.add(report)
    db.commit()
    return RedirectResponse(f"/status-reports/{report_id}/view", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/programs/{program_id}/status-reports/create", include_in_schema=False)
async def create_status_report_from_ui(
    program_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    program = db.scalars(
        select(Program)
        .options(
            selectinload(Program.work_items),
            selectinload(Program.dependencies),
            selectinload(Program.risks),
        )
        .where(Program.id == program_id)
    ).one_or_none()
    if program is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")

    parsed = await _parse_form(request)
    reported_health = parsed.get("reported_health", "")
    report_date_str = parsed.get("report_date", "")
    if reported_health not in STATUS_REPORT_HEALTHS or not report_date_str:
        query = urlencode({
            "show_new_report": "1",
            "report_error": "Report date and health status are required.",
        })
        return RedirectResponse(
            f"/programs/{program_id}/view?{query}#new-report",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    from datetime import date as _date
    report_date = _date.fromisoformat(report_date_str)
    week = report_date.isocalendar().week
    report = StatusReport(
        program_id=program_id,
        report_date=report_date,
        report_title=f"Week {week} {program.name} Report",
        reported_health=reported_health,
        suggested_health=compute_suggested_health(program),
        summary=parsed.get("summary", "").strip() or None,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return RedirectResponse(f"/status-reports/{report.id}/view", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/status-reports/{report_id}/update", include_in_schema=False)
async def update_status_report_from_ui(
    report_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    report = db.get(StatusReport, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Status report not found")

    parsed = await _parse_form(request)
    reported_health = parsed.get("reported_health", report.reported_health)
    report_date_str = parsed.get("report_date", "")
    if reported_health in STATUS_REPORT_HEALTHS:
        report.reported_health = reported_health
    if report_date_str:
        from datetime import date as _date
        report.report_date = _date.fromisoformat(report_date_str)
    report.summary = parsed.get("summary", "").strip() or None
    db.add(report)
    db.commit()
    if parsed.get("return_to") == "detail":
        return RedirectResponse(f"/status-reports/{report_id}/view", status_code=status.HTTP_303_SEE_OTHER)
    return RedirectResponse(f"/programs/{report.program_id}/view", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/status-reports/{report_id}/delete/confirm", response_class=HTMLResponse, include_in_schema=False)
def confirm_delete_status_report_page(
    request: Request, report_id: int, db: Session = Depends(get_db)
) -> HTMLResponse:
    report = db.get(StatusReport, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Status report not found")
    return templates.TemplateResponse(
        request,
        "confirm_delete.html",
        {
            "page_title": "Delete Status Report?",
            "subtitle": f"{report.report_date} — {report.reported_health.replace('_', ' ').title()}",
            "back_url": f"/programs/{report.program_id}/view",
            "back_label": "Back to Program",
            "message": "This permanently removes the status report.",
            "action_url": f"/status-reports/{report.id}/delete",
            "cancel_url": f"/programs/{report.program_id}/view",
        },
    )


@router.post("/status-reports/{report_id}/delete", include_in_schema=False)
def delete_status_report_from_ui(report_id: int, db: Session = Depends(get_db)) -> RedirectResponse:
    report = db.get(StatusReport, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Status report not found")
    program_id = report.program_id
    db.delete(report)
    db.commit()
    return RedirectResponse(f"/programs/{program_id}/view", status_code=status.HTTP_303_SEE_OTHER)


# ── Milestone UI handlers ────────────────────────────────────────────────────

@router.post("/programs/{program_id}/milestones/create", include_in_schema=False)
async def create_milestone_from_ui(
    program_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    if db.get(Program, program_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")

    parsed = await _parse_form(request)
    title = parsed.get("title", "").strip()
    milestone_status = parsed.get("status", "planned")
    if not title or milestone_status not in MILESTONE_STATUSES:
        query = urlencode({"show_new_milestone": "1", "milestone_error": "Title and status are required."})
        return RedirectResponse(
            f"/programs/{program_id}/view?{query}#new-milestone",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    db.add(Milestone(
        program_id=program_id,
        title=title,
        description=parsed.get("description", "").strip() or None,
        target_date=_parse_due_date(parsed.get("target_date", "")),
        status=milestone_status,
    ))
    db.commit()
    return RedirectResponse(f"/programs/{program_id}/view", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/milestones/{milestone_id}/update", include_in_schema=False)
async def update_milestone_from_ui(
    milestone_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    milestone = db.get(Milestone, milestone_id)
    if milestone is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Milestone not found")

    parsed = await _parse_form(request)
    title = parsed.get("title", "").strip()
    milestone_status = parsed.get("status", milestone.status)
    if title and milestone_status in MILESTONE_STATUSES:
        milestone.title = title
        milestone.description = parsed.get("description", "").strip() or None
        milestone.target_date = _parse_due_date(parsed.get("target_date", ""))
        milestone.status = milestone_status
        db.add(milestone)
        db.commit()
    return_to = parsed.get("return_to", "")
    if return_to and return_to.startswith("/"):
        return RedirectResponse(return_to, status_code=status.HTTP_303_SEE_OTHER)
    return RedirectResponse(f"/programs/{milestone.program_id}/view", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/milestones/{milestone_id}/achieve-ui", include_in_schema=False)
def achieve_milestone_from_ui(milestone_id: int, db: Session = Depends(get_db)) -> RedirectResponse:
    milestone = db.get(Milestone, milestone_id)
    if milestone is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Milestone not found")
    milestone.status = "achieved"
    db.add(milestone)
    db.commit()
    return RedirectResponse(f"/programs/{milestone.program_id}/view", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/milestones/{milestone_id}/delete/confirm", response_class=HTMLResponse, include_in_schema=False)
def confirm_delete_milestone_page(
    request: Request, milestone_id: int, db: Session = Depends(get_db)
) -> HTMLResponse:
    milestone = db.get(Milestone, milestone_id)
    if milestone is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Milestone not found")
    return templates.TemplateResponse(
        request,
        "confirm_delete.html",
        {
            "page_title": "Delete Milestone?",
            "subtitle": milestone.title,
            "back_url": f"/programs/{milestone.program_id}/view",
            "back_label": "Back to Program",
            "message": "This removes the Milestone from the Program.",
            "action_url": f"/milestones/{milestone.id}/delete",
            "cancel_url": f"/programs/{milestone.program_id}/view",
        },
    )


@router.post("/milestones/{milestone_id}/delete", include_in_schema=False)
def delete_milestone_from_ui(milestone_id: int, db: Session = Depends(get_db)) -> RedirectResponse:
    milestone = db.get(Milestone, milestone_id)
    if milestone is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Milestone not found")
    program_id = milestone.program_id
    db.delete(milestone)
    db.commit()
    return RedirectResponse(f"/programs/{program_id}/view", status_code=status.HTTP_303_SEE_OTHER)


# ── Decision UI handlers ──────────────────────────────────────────────────────

@router.post("/programs/{program_id}/decisions/create", include_in_schema=False)
async def create_decision_from_ui(
    program_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    if db.get(Program, program_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")

    parsed = await _parse_form(request)
    title = parsed.get("title", "").strip()
    decision_status = parsed.get("status", "proposed")
    if not title or decision_status not in DECISION_STATUSES:
        query = urlencode({"show_new_decision": "1", "decision_error": "Title and status are required."})
        return RedirectResponse(
            f"/programs/{program_id}/view?{query}#new-decision",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    db.add(Decision(
        program_id=program_id,
        title=title,
        description=parsed.get("description", "").strip() or None,
        decision_date=_parse_due_date(parsed.get("decision_date", "")),
        status=decision_status,
        owner=parsed.get("owner", "").strip() or None,
        rationale=parsed.get("rationale", "").strip() or None,
    ))
    db.commit()
    return RedirectResponse(f"/programs/{program_id}/view", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/decisions/{decision_id}/update", include_in_schema=False)
async def update_decision_from_ui(
    decision_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    decision = db.get(Decision, decision_id)
    if decision is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Decision not found")

    parsed = await _parse_form(request)
    title = parsed.get("title", "").strip()
    decision_status = parsed.get("status", decision.status)
    if title and decision_status in DECISION_STATUSES:
        decision.title = title
        decision.description = parsed.get("description", "").strip() or None
        decision.decision_date = _parse_due_date(parsed.get("decision_date", ""))
        decision.status = decision_status
        decision.owner = parsed.get("owner", "").strip() or None
        decision.rationale = parsed.get("rationale", "").strip() or None
        db.add(decision)
        db.commit()
    return_to = parsed.get("return_to", "")
    if return_to and return_to.startswith("/"):
        return RedirectResponse(return_to, status_code=status.HTTP_303_SEE_OTHER)
    return RedirectResponse(f"/programs/{decision.program_id}/view", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/decisions/{decision_id}/decide-ui", include_in_schema=False)
def decide_decision_from_ui(decision_id: int, db: Session = Depends(get_db)) -> RedirectResponse:
    decision = db.get(Decision, decision_id)
    if decision is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Decision not found")
    decision.status = "decided"
    db.add(decision)
    db.commit()
    return RedirectResponse(f"/programs/{decision.program_id}/view", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/decisions/{decision_id}/delete/confirm", response_class=HTMLResponse, include_in_schema=False)
def confirm_delete_decision_page(
    request: Request, decision_id: int, db: Session = Depends(get_db)
) -> HTMLResponse:
    decision = db.get(Decision, decision_id)
    if decision is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Decision not found")
    return templates.TemplateResponse(
        request,
        "confirm_delete.html",
        {
            "page_title": "Delete Decision?",
            "subtitle": decision.title,
            "back_url": f"/programs/{decision.program_id}/view",
            "back_label": "Back to Program",
            "message": "This removes the Decision from the Program.",
            "action_url": f"/decisions/{decision.id}/delete",
            "cancel_url": f"/programs/{decision.program_id}/view",
        },
    )


@router.post("/decisions/{decision_id}/delete", include_in_schema=False)
def delete_decision_from_ui(decision_id: int, db: Session = Depends(get_db)) -> RedirectResponse:
    decision = db.get(Decision, decision_id)
    if decision is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Decision not found")
    program_id = decision.program_id
    db.delete(decision)
    db.commit()
    return RedirectResponse(f"/programs/{program_id}/view", status_code=status.HTTP_303_SEE_OTHER)


# ── Requirement UI handlers ───────────────────────────────────────────────────

@router.post("/programs/{program_id}/requirements/create", include_in_schema=False)
async def create_requirement_from_ui(
    program_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    if db.get(Program, program_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")

    parsed = await _parse_form(request)
    title = parsed.get("title", "").strip()
    req_source_type = parsed.get("source_type", "other")
    req_status = parsed.get("status", "proposed")
    if not title or req_source_type not in REQUIREMENT_SOURCE_TYPES or req_status not in REQUIREMENT_STATUSES:
        query = urlencode({"show_new_requirement": "1", "requirement_error": "Title, source type, and status are required."})
        return RedirectResponse(
            f"/programs/{program_id}/view?{query}#new-requirement",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    db.add(Requirement(
        program_id=program_id,
        title=title,
        description=parsed.get("description", "").strip() or None,
        source_type=req_source_type,
        status=req_status,
        owner=parsed.get("owner", "").strip() or None,
        target_date=_parse_due_date(parsed.get("target_date", "")),
        link=parsed.get("link", "").strip() or None,
    ))
    db.commit()
    return RedirectResponse(f"/programs/{program_id}/view", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/requirements/{requirement_id}/update", include_in_schema=False)
async def update_requirement_from_ui(
    requirement_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    requirement = db.get(Requirement, requirement_id)
    if requirement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requirement not found")

    parsed = await _parse_form(request)
    title = parsed.get("title", "").strip()
    req_source_type = parsed.get("source_type", requirement.source_type)
    req_status = parsed.get("status", requirement.status)
    if title and req_source_type in REQUIREMENT_SOURCE_TYPES and req_status in REQUIREMENT_STATUSES:
        requirement.title = title
        requirement.description = parsed.get("description", "").strip() or None
        requirement.source_type = req_source_type
        requirement.status = req_status
        requirement.owner = parsed.get("owner", "").strip() or None
        requirement.target_date = _parse_due_date(parsed.get("target_date", ""))
        requirement.link = parsed.get("link", "").strip() or None
        db.add(requirement)
        db.commit()
    return_to = parsed.get("return_to", "")
    if return_to and return_to.startswith("/"):
        return RedirectResponse(return_to, status_code=status.HTTP_303_SEE_OTHER)
    return RedirectResponse(f"/programs/{requirement.program_id}/view", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/requirements/{requirement_id}/deliver-ui", include_in_schema=False)
def deliver_requirement_from_ui(requirement_id: int, db: Session = Depends(get_db)) -> RedirectResponse:
    requirement = db.get(Requirement, requirement_id)
    if requirement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requirement not found")
    requirement.status = "delivered"
    db.add(requirement)
    db.commit()
    return RedirectResponse(f"/programs/{requirement.program_id}/view", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/requirements/{requirement_id}/delete/confirm", response_class=HTMLResponse, include_in_schema=False)
def confirm_delete_requirement_page(
    request: Request, requirement_id: int, db: Session = Depends(get_db)
) -> HTMLResponse:
    requirement = db.get(Requirement, requirement_id)
    if requirement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requirement not found")
    return templates.TemplateResponse(
        request,
        "confirm_delete.html",
        {
            "page_title": "Delete Requirement?",
            "subtitle": requirement.title,
            "back_url": f"/programs/{requirement.program_id}/view",
            "back_label": "Back to Program",
            "message": "This removes the Requirement from the Program.",
            "action_url": f"/requirements/{requirement.id}/delete",
            "cancel_url": f"/programs/{requirement.program_id}/view",
        },
    )


@router.post("/requirements/{requirement_id}/delete", include_in_schema=False)
def delete_requirement_from_ui(requirement_id: int, db: Session = Depends(get_db)) -> RedirectResponse:
    requirement = db.get(Requirement, requirement_id)
    if requirement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requirement not found")
    program_id = requirement.program_id
    db.delete(requirement)
    db.commit()
    return RedirectResponse(f"/programs/{program_id}/view", status_code=status.HTTP_303_SEE_OTHER)


# ── Feature UI handlers ───────────────────────────────────────────────────────

@router.post("/programs/{program_id}/features/create", include_in_schema=False)
async def create_feature_from_ui(
    program_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    if db.get(Program, program_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")

    parsed = await _parse_form(request)
    title = parsed.get("title", "").strip()
    feature_status = parsed.get("status", "proposed")
    if not title or feature_status not in FEATURE_STATUSES:
        query = urlencode({"show_new_feature": "1", "feature_error": "Title and status are required."})
        return RedirectResponse(
            f"/programs/{program_id}/view?{query}#new-feature",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    db.add(Feature(
        program_id=program_id,
        title=title,
        description=parsed.get("description", "").strip() or None,
        status=feature_status,
        owner=parsed.get("owner", "").strip() or None,
        target_date=_parse_due_date(parsed.get("target_date", "")),
        link=parsed.get("link", "").strip() or None,
    ))
    db.commit()
    return RedirectResponse(f"/programs/{program_id}/view", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/features/{feature_id}/update", include_in_schema=False)
async def update_feature_from_ui(
    feature_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    feature = db.get(Feature, feature_id)
    if feature is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feature not found")

    parsed = await _parse_form(request)
    title = parsed.get("title", "").strip()
    feature_status = parsed.get("status", feature.status)
    if title and feature_status in FEATURE_STATUSES:
        feature.title = title
        feature.description = parsed.get("description", "").strip() or None
        feature.status = feature_status
        feature.owner = parsed.get("owner", "").strip() or None
        feature.target_date = _parse_due_date(parsed.get("target_date", ""))
        feature.link = parsed.get("link", "").strip() or None
        db.add(feature)
        db.commit()
    return_to = parsed.get("return_to", "")
    if return_to and return_to.startswith("/"):
        return RedirectResponse(return_to, status_code=status.HTTP_303_SEE_OTHER)
    return RedirectResponse(f"/programs/{feature.program_id}/view", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/features/{feature_id}/deliver-ui", include_in_schema=False)
def deliver_feature_from_ui(feature_id: int, db: Session = Depends(get_db)) -> RedirectResponse:
    feature = db.get(Feature, feature_id)
    if feature is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feature not found")
    feature.status = "delivered"
    db.add(feature)
    db.commit()
    return RedirectResponse(f"/programs/{feature.program_id}/view", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/features/{feature_id}/delete/confirm", response_class=HTMLResponse, include_in_schema=False)
def confirm_delete_feature_page(
    request: Request, feature_id: int, db: Session = Depends(get_db)
) -> HTMLResponse:
    feature = db.get(Feature, feature_id)
    if feature is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feature not found")
    return templates.TemplateResponse(
        request,
        "confirm_delete.html",
        {
            "page_title": "Delete Feature?",
            "subtitle": feature.title,
            "back_url": f"/programs/{feature.program_id}/view",
            "back_label": "Back to Program",
            "message": "This removes the Feature from the Program.",
            "action_url": f"/features/{feature.id}/delete",
            "cancel_url": f"/programs/{feature.program_id}/view",
        },
    )


@router.post("/features/{feature_id}/delete", include_in_schema=False)
def delete_feature_from_ui(feature_id: int, db: Session = Depends(get_db)) -> RedirectResponse:
    feature = db.get(Feature, feature_id)
    if feature is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feature not found")
    program_id = feature.program_id
    db.delete(feature)
    db.commit()
    return RedirectResponse(f"/programs/{program_id}/view", status_code=status.HTTP_303_SEE_OTHER)


# ── Relationship UI handlers ──────────────────────────────────────────────────

_VALID_OBJECT_TYPES = frozenset(_RELATIONSHIP_OBJECT_MODEL_MAP.keys())


@router.post("/programs/{program_id}/relationships/create", include_in_schema=False)
async def create_relationship_from_ui(
    program_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    if db.get(Program, program_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")

    parsed = await _parse_form(request)
    source_ref = parsed.get("source_ref", "")
    target_ref = parsed.get("target_ref", "")
    relationship_type = parsed.get("relationship_type", "")
    note = parsed.get("note", "").strip() or None

    def _error(msg: str) -> RedirectResponse:
        query = urlencode({"show_new_relationship": "1", "relationship_error": msg})
        return RedirectResponse(
            f"/programs/{program_id}/view?{query}#new-relationship",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    if ":" not in source_ref or ":" not in target_ref:
        return _error("Source and target are required.")
    source_type, _, source_id_str = source_ref.partition(":")
    target_type, _, target_id_str = target_ref.partition(":")
    if source_type not in _VALID_OBJECT_TYPES or target_type not in _VALID_OBJECT_TYPES:
        return _error("Invalid object type.")
    if relationship_type not in RELATIONSHIP_TYPES:
        return _error("Invalid relationship type.")
    try:
        source_id = int(source_id_str)
        target_id = int(target_id_str)
    except ValueError:
        return _error("Invalid object reference.")
    if source_type == target_type and source_id == target_id:
        return _error("Source and target cannot be the same object.")
    source_model = _RELATIONSHIP_OBJECT_MODEL_MAP[source_type]
    target_model = _RELATIONSHIP_OBJECT_MODEL_MAP[target_type]
    if db.get(source_model, source_id) is None:
        return _error("Source object not found.")
    if db.get(target_model, target_id) is None:
        return _error("Target object not found.")

    from app.models.relationship import Relationship as _Rel
    db.add(_Rel(
        source_type=source_type,
        source_id=source_id,
        relationship_type=relationship_type,
        target_type=target_type,
        target_id=target_id,
        note=note,
    ))
    db.commit()
    return RedirectResponse(f"/programs/{program_id}/view", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/relationships/{relationship_id}/delete-ui", include_in_schema=False)
async def delete_relationship_from_ui(
    relationship_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    parsed = await _parse_form(request)
    program_id_str = parsed.get("program_id", "")
    rel = db.get(Relationship, relationship_id)
    if rel is not None:
        db.delete(rel)
        db.commit()
    try:
        program_id = int(program_id_str)
    except (ValueError, TypeError):
        return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    return RedirectResponse(f"/programs/{program_id}/view", status_code=status.HTTP_303_SEE_OTHER)


# ── Unified Settings page ──────────────────────────────────────────────────────

@router.get("/settings", response_class=HTMLResponse, include_in_schema=False)
def settings_page(
    request: Request,
    edit_status_id: Optional[int] = None,
    edit_source_type_id: Optional[int] = None,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    seed_default_program_statuses(db)

    all_statuses = list(
        db.scalars(select(ProgramStatus).order_by(ProgramStatus.sort_order.asc(), ProgramStatus.id.asc()))
    )
    source_types = list(
        db.scalars(select(SourceType).order_by(SourceType.sort_order.asc(), SourceType.id.asc()))
    )

    return templates.TemplateResponse(
        request,
        "settings.html",
        {
            "all_statuses": all_statuses,
            "source_types": source_types,
            "edit_status_id": edit_status_id,
            "edit_source_type_id": edit_source_type_id,
        },
    )


# ── Redirects for old settings URLs ──────────────────────────────────────────

@router.get("/settings/source-types", include_in_schema=False)
def redirect_source_types_settings() -> RedirectResponse:
    return RedirectResponse("/settings#source-types", status_code=301)


@router.get("/settings/program-statuses", include_in_schema=False)
def redirect_program_statuses_settings() -> RedirectResponse:
    return RedirectResponse("/settings#program-statuses", status_code=301)


# ── Settings POST handlers ────────────────────────────────────────────────────

@router.post("/settings/source-types/create", include_in_schema=False)
async def create_source_type_from_ui(request: Request, db: Session = Depends(get_db)) -> RedirectResponse:
    import re as _re
    parsed = await _parse_form(request)
    name = parsed.get("name", "").strip()
    slug_raw = parsed.get("slug", "").strip()
    slug = _re.sub(r"[^a-z0-9]+", "-", (slug_raw or name).lower()).strip("-")
    if name and slug:
        existing = db.scalar(select(SourceType).where(SourceType.slug == slug))
        if existing is None:
            max_order = db.scalar(select(func.max(SourceType.sort_order))) or -1
            db.add(SourceType(name=name, slug=slug, sort_order=max_order + 1))
            db.commit()
    return RedirectResponse("/settings#source-types", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/settings/source-types/reorder", include_in_schema=False)
async def reorder_source_types(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    for i, st_id in enumerate(data.get("ids", [])):
        st = db.get(SourceType, int(st_id))
        if st:
            st.sort_order = i
    db.commit()
    return {"ok": True}


@router.post("/settings/source-types/{source_type_id}/update", include_in_schema=False)
async def update_source_type_from_ui(
    source_type_id: int, request: Request, db: Session = Depends(get_db)
) -> RedirectResponse:
    source_type = db.get(SourceType, source_type_id)
    if source_type is not None:
        parsed = await _parse_form(request)
        name = parsed.get("name", "").strip()
        if name:
            source_type.name = name
            db.add(source_type)
            db.commit()
    return RedirectResponse("/settings#source-types", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/settings/source-types/{source_type_id}/delete", include_in_schema=False)
def delete_source_type_from_ui(source_type_id: int, db: Session = Depends(get_db)) -> RedirectResponse:
    source_type = db.get(SourceType, source_type_id)
    if source_type is not None:
        db.delete(source_type)
        db.commit()
    return RedirectResponse("/settings#source-types", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/settings/program-statuses/create", include_in_schema=False)
async def create_program_status_from_ui(
    request: Request, db: Session = Depends(get_db)
) -> RedirectResponse:
    parsed = await _parse_form(request)
    name = parsed.get("name", "").strip()
    slug = parsed.get("slug", "").strip().lower().replace(" ", "-")
    color = parsed.get("color", "#6b7280").strip() or "#6b7280"
    is_operational = parsed.get("is_operational", "0") == "1"
    if name and slug:
        existing = db.scalar(select(ProgramStatus).where(ProgramStatus.slug == slug))
        if existing is None:
            max_order = db.scalar(select(func.max(ProgramStatus.sort_order))) or -1
            db.add(ProgramStatus(name=name, slug=slug, color=color, sort_order=max_order + 1, is_operational=is_operational))
            db.commit()
    return RedirectResponse("/settings#program-statuses", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/settings/program-statuses/reorder", include_in_schema=False)
async def reorder_program_statuses(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    for i, ps_id in enumerate(data.get("ids", [])):
        ps = db.get(ProgramStatus, int(ps_id))
        if ps:
            ps.sort_order = i
    db.commit()
    return {"ok": True}


@router.post("/settings/program-statuses/{status_id}/update", include_in_schema=False)
async def update_program_status_from_ui(
    status_id: int, request: Request, db: Session = Depends(get_db)
) -> RedirectResponse:
    ps = db.get(ProgramStatus, status_id)
    if ps is not None:
        parsed = await _parse_form(request)
        name = parsed.get("name", "").strip()
        slug = parsed.get("slug", "").strip().lower().replace(" ", "-") or ps.slug
        color = parsed.get("color", "").strip() or ps.color
        is_default = parsed.get("is_default", "0") == "1"
        is_operational = parsed.get("is_operational", "0") == "1"
        if name:
            slug_conflict = db.scalar(
                select(ProgramStatus).where(ProgramStatus.slug == slug, ProgramStatus.id != status_id)
            )
            if slug_conflict is None:
                ps.slug = slug
            if is_default:
                db.execute(
                    update(ProgramStatus).where(ProgramStatus.id != status_id).values(is_default=False)
                )
            ps.name = name
            ps.color = color
            ps.is_default = is_default
            ps.is_operational = is_operational
            db.add(ps)
            db.commit()
    return RedirectResponse("/settings#program-statuses", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/settings/program-statuses/{status_id}/delete", include_in_schema=False)
def delete_program_status_from_ui(status_id: int, db: Session = Depends(get_db)) -> RedirectResponse:
    ps = db.get(ProgramStatus, status_id)
    if ps is None:
        return RedirectResponse("/settings#program-statuses", status_code=status.HTTP_303_SEE_OTHER)

    replacement = db.scalar(
        select(ProgramStatus)
        .where(ProgramStatus.id != status_id)
        .order_by(ProgramStatus.sort_order.asc(), ProgramStatus.id.asc())
    )
    if replacement is None:
        return RedirectResponse("/settings#program-statuses", status_code=status.HTTP_303_SEE_OTHER)

    if ps.is_default:
        replacement.is_default = True

    for prog in list(db.scalars(select(Program).where(Program.status_id == status_id))):
        prog.status_id = replacement.id

    db.flush()
    db.delete(ps)
    db.commit()
    return RedirectResponse("/settings#program-statuses", status_code=status.HTTP_303_SEE_OTHER)


# ── Morning View ──────────────────────────────────────────────────────────────

@router.get("/morning", response_class=HTMLResponse, include_in_schema=False)
def morning_view(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    health_buckets = get_programs_by_health(db)
    return templates.TemplateResponse(
        request,
        "morning.html",
        {
            "today": date.today(),
            "programs_off_track": health_buckets["off_track"],
            "programs_at_risk": health_buckets["at_risk"],
            "programs_needing_attention": health_buckets["needs_attention"],
            "blocked_work_items": get_blocked_work_items(db),
            "blocked_dependencies": get_blocked_dependencies(db),
            "overdue_work_items": get_overdue_work_items(db),
            "stale_work_items": get_stale_work_items(db),
            "critical_dependencies": get_critical_dependencies(db),
            "stale_dependencies": get_stale_dependencies(db),
            "critical_risks": get_critical_risks(db),
            "stale_risks": get_stale_risks(db),
            "recently_updated_programs": get_recently_updated_programs(db),
        },
    )
