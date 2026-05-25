from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.domain.dependencies import dependency_is_stale
from app.domain.programs import program_attention_state, work_item_is_overdue, work_item_is_stale
from app.domain.queries import (
    get_blocked_dependencies,
    get_blocked_work_items,
    get_critical_dependencies,
    get_overdue_work_items,
    get_programs_needing_attention,
    get_recently_updated_programs,
    get_stale_dependencies,
    get_stale_work_items,
)
from app.models import Dependency, Program, ProgramStatus, SourceType, WorkItem
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
ATTENTION_STATES = ("Needs attention", "OK")
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
        "program_attention_state": program_attention_state,
        "work_item_is_overdue": work_item_is_overdue,
        "work_item_is_stale": work_item_is_stale,
        "dependency_is_stale": dependency_is_stale,
        "WORK_ITEM_STATUSES": WORK_ITEM_STATUSES,
        "WORK_ITEM_PRIORITIES": WORK_ITEM_PRIORITIES,
        "DEPENDENCY_TYPES": DEPENDENCY_TYPES,
        "DEPENDENCY_STATUSES": DEPENDENCY_STATUSES,
        "BLOCKING_LEVELS": BLOCKING_LEVELS,
        "WORK_ITEM_SORT_LABELS": WORK_ITEM_SORT_LABELS,
        "DEPENDENCY_SORT_LABELS": DEPENDENCY_SORT_LABELS,
        "ATTENTION_STATES": ATTENTION_STATES,
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
    attention_filter: Optional[str] = None,
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
    if attention_filter and attention_filter not in ATTENTION_STATES:
        attention_filter = None
    if sort not in PROGRAM_SORTS and sort != "status":
        sort = "updated_at"

    statement = select(Program).options(selectinload(Program.work_items))
    if status_filter:
        statement = statement.join(Program.program_status).where(ProgramStatus.slug == status_filter)
    if sort == "status":
        if not status_filter:
            statement = statement.join(Program.program_status)
        statement = statement.order_by(ProgramStatus.sort_order.asc(), Program.id.desc())
    else:
        statement = statement.order_by(PROGRAM_SORTS[sort], Program.id.desc())
    programs = list(db.scalars(statement))
    if attention_filter:
        programs = [p for p in programs if program_attention_state(p) == attention_filter]

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "all_statuses": all_statuses,
            "programs": programs,
            "status_filter": status_filter,
            "attention_filter": attention_filter,
            "sort": sort,
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
    db.add(Program(name=name, description=description, status_id=ps.id))
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
    db: Session = Depends(get_db),
) -> HTMLResponse:
    program = db.scalars(
        select(Program)
        .options(
            selectinload(Program.work_items).selectinload(WorkItem.source_type),
            selectinload(Program.dependencies),
        )
        .where(Program.id == program_id)
    ).one_or_none()
    if program is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")
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

    work_owners = sorted({item.owner for item in program.work_items if item.owner})
    dep_owners = sorted({item.owner for item in program.dependencies if item.owner})

    return templates.TemplateResponse(
        request,
        "program_detail.html",
        {
            "program": program,
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
    if name and slug:
        existing = db.scalar(select(ProgramStatus).where(ProgramStatus.slug == slug))
        if existing is None:
            max_order = db.scalar(select(func.max(ProgramStatus.sort_order))) or -1
            db.add(ProgramStatus(name=name, slug=slug, color=color, sort_order=max_order + 1))
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
    return templates.TemplateResponse(
        request,
        "morning.html",
        {
            "today": date.today(),
            "programs_needing_attention": get_programs_needing_attention(db),
            "blocked_work_items": get_blocked_work_items(db),
            "blocked_dependencies": get_blocked_dependencies(db),
            "overdue_work_items": get_overdue_work_items(db),
            "stale_work_items": get_stale_work_items(db),
            "critical_dependencies": get_critical_dependencies(db),
            "stale_dependencies": get_stale_dependencies(db),
            "recently_updated_programs": get_recently_updated_programs(db),
        },
    )
