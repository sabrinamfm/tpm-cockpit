from datetime import date, datetime, timezone
from html import escape
from typing import Optional
from urllib.parse import parse_qs, urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.domain.dependencies import dependency_is_stale
from app.domain.programs import program_attention_state, work_item_is_overdue, work_item_is_stale
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


def _format_datetime(value) -> str:
    return value.strftime("%Y-%m-%d %H:%M") if value else ""


def _format_date(value) -> str:
    return value.isoformat() if value else ""


async def _parse_form(request: Request) -> dict[str, str]:
    form_data = await request.body()
    parsed = parse_qs(form_data.decode())
    return {key: values[0] for key, values in parsed.items()}


def _select_option(value: str, label: str, selected: Optional[str]) -> str:
    selected_attr = " selected" if value == selected else ""
    return f'<option value="{escape(value)}"{selected_attr}>{escape(label)}</option>'


def _program_status_options(
    statuses: list[ProgramStatus],
    selected_slug: Optional[str] = None,
    include_all: bool = False,
) -> str:
    parts = ['<option value="">All statuses</option>'] if include_all else []
    for ps in statuses:
        if not ps.is_active and ps.slug != selected_slug:
            continue
        label = ps.name if ps.is_active else f"{ps.name} (inactive)"
        parts.append(_select_option(ps.slug, label, selected_slug))
    return "".join(parts)


def _source_type_options(
    source_types: list[SourceType],
    selected_id: Optional[int] = None,
    include_inactive_selected: bool = True,
) -> str:
    options = [_select_option("", "No source", str(selected_id) if selected_id is not None else "")]
    for source_type in source_types:
        if not source_type.is_active and not (include_inactive_selected and source_type.id == selected_id):
            continue
        label = source_type.name if source_type.is_active else f"{source_type.name} (inactive)"
        options.append(_select_option(str(source_type.id), label, str(selected_id) if selected_id else None))
    return "".join(options)


def _query_string(**params: str) -> str:
    clean_params = {key: value for key, value in params.items() if value}
    return f"?{urlencode(clean_params)}" if clean_params else ""


def _page_shell(title: str, body: str) -> str:
    return f"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)} · TPM Cockpit</title>
  <style>
    :root {{
      color-scheme: light;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: #18212f;
      background: #f5f6f8;
    }}
    body {{ margin: 0; }}
    main {{ max-width: 1220px; margin: 0 auto; padding: 32px 20px 48px; }}
    header {{ display: flex; align-items: end; justify-content: space-between; gap: 20px; margin-bottom: 24px; }}
    h1 {{ margin: 0; font-size: 30px; font-weight: 720; }}
    h2 {{ margin: 0 0 14px; font-size: 18px; }}
    h3 {{ margin: 0 0 8px; font-size: 15px; }}
    a {{ color: #2364aa; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .top-links {{ display: flex; gap: 12px; flex-wrap: wrap; justify-content: flex-end; }}
    .muted {{ color: #667085; }}
    .layout {{ display: grid; grid-template-columns: minmax(280px, 340px) 1fr; gap: 20px; align-items: start; }}
    .panel {{ background: #ffffff; border: 1px solid #d9dee7; border-radius: 8px; padding: 18px; }}
    label {{ display: block; margin: 12px 0 6px; font-size: 13px; font-weight: 650; }}
    input, textarea, select {{
      width: 100%;
      box-sizing: border-box;
      border: 1px solid #c8d0dc;
      border-radius: 6px;
      padding: 9px 10px;
      font: inherit;
      background: #ffffff;
    }}
    textarea {{ min-height: 92px; resize: vertical; }}
    button, .button {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border: 0;
      border-radius: 6px;
      padding: 9px 12px;
      font: inherit;
      font-weight: 650;
      cursor: pointer;
      background: #2364aa;
      color: #ffffff;
      text-decoration: none;
    }}
    button.secondary, .button.secondary {{ background: #e7ebf1; color: #243043; }}
    button.danger, .button.danger {{ background: #b42318; color: #ffffff; }}
    .actions {{ display: flex; gap: 8px; margin-top: 14px; flex-wrap: wrap; }}
    .filters {{ display: grid; grid-template-columns: repeat(4, minmax(120px, 1fr)); gap: 12px; align-items: end; margin-bottom: 16px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ padding: 10px; border-bottom: 1px solid #e2e7ef; text-align: left; vertical-align: top; font-size: 14px; }}
    th {{ color: #526071; font-size: 12px; text-transform: uppercase; }}
    .row-actions {{ min-width: 96px; }}
    details.action-menu {{ position: relative; display: inline-block; }}
    details.action-menu summary {{ list-style: none; }}
    details.action-menu summary::-webkit-details-marker {{ display: none; }}
    .menu {{
      position: absolute;
      right: 0;
      z-index: 2;
      min-width: 130px;
      margin-top: 6px;
      padding: 8px;
      background: #ffffff;
      border: 1px solid #cfd6e3;
      border-radius: 8px;
      box-shadow: 0 8px 24px rgba(16, 24, 40, 0.12);
    }}
    .menu a, .menu button {{
      display: block;
      width: 100%;
      box-sizing: border-box;
      padding: 7px 8px;
      border-radius: 6px;
      background: transparent;
      color: #2364aa;
      text-align: left;
      font-weight: 400;
    }}
    .menu a:hover, .menu button:hover {{ background: #f2f5f9; text-decoration: none; }}
    .pill {{ display: inline-block; border-radius: 999px; padding: 3px 8px; font-size: 12px; font-weight: 700; background: #eef2f7; color: #344054; }}
    .attention {{ background: #fff3cd; color: #7a4d00; }}
    .ok {{ background: #e7f5ec; color: #246b3d; }}
    .blocked-row {{ background: #fff4f3; }}
    .overdue-row {{ background: #fff7ed; }}
    .stale-row {{ background: #fffbeb; }}
    .critical-row {{ background: #fef3f2; }}
    .detail-grid {{ display: grid; grid-template-columns: repeat(2, minmax(180px, 1fr)); gap: 12px; margin: 16px 0; }}
    .placeholder-grid {{ display: grid; grid-template-columns: repeat(2, minmax(220px, 1fr)); gap: 14px; }}
    .placeholder {{ min-height: 86px; }}
    .settings-nav {{ display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 28px; }}
    .settings-nav a {{ display: inline-block; padding: 6px 14px; border-radius: 6px; background: #e7ebf1; color: #243043; font-size: 13px; font-weight: 600; text-decoration: none; }}
    .settings-nav a:hover {{ background: #d9dee7; }}
    .drag-handle {{ cursor: grab; color: #9ca3af; user-select: none; font-size: 16px; padding: 0 4px; }}
    .drag-handle:active {{ cursor: grabbing; }}
    .settings-section {{ margin-bottom: 40px; }}
    .settings-section-header {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }}
    .settings-section-header h2 {{ margin: 0; }}
    details.create-panel > summary {{ list-style: none; cursor: pointer; }}
    details.create-panel > summary::-webkit-details-marker {{ display: none; }}
    details.create-panel > .panel {{ margin-top: 10px; }}
    .compact-fields {{ display: grid; grid-template-columns: repeat(3, minmax(120px, 1fr)); gap: 8px; }}
    .collapsible-panel {{
      margin-bottom: 16px;
      border: 1px solid #d9dee7;
      border-radius: 8px;
      background: #ffffff;
    }}
    .collapsible-panel > summary {{
      display: inline-flex;
      margin: 18px;
      list-style: none;
    }}
    .collapsible-panel > summary::-webkit-details-marker {{ display: none; }}
    .collapsible-body {{ padding: 0 18px 18px; }}
    .error {{ color: #b42318; font-weight: 650; margin-bottom: 10px; }}
    @media (max-width: 900px) {{
      header, .layout {{ display: block; }}
      .panel {{ margin-bottom: 18px; }}
      .filters, .detail-grid, .placeholder-grid, .compact-fields {{ grid-template-columns: 1fr; }}
      th:nth-child(2), td:nth-child(2), th:nth-child(7), td:nth-child(7) {{ display: none; }}
    }}
  </style>
</head>
<body>
  <main>
    {body}
  </main>
</body>
</html>
"""


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def program_ui(
    status_filter: Optional[str] = None,
    attention_filter: Optional[str] = None,
    sort: str = "updated_at",
    db: Session = Depends(get_db),
) -> str:
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
        programs = [
            program for program in programs if program_attention_state(program) == attention_filter
        ]

    status_options = _program_status_options(all_statuses, status_filter, include_all=True)
    attention_options = '<option value="">All attention states</option>' + "".join(
        _select_option(attention, attention, attention_filter) for attention in ATTENTION_STATES
    )
    sort_options = "".join(
        _select_option(value, label, sort)
        for value, label in (
            ("updated_at", "Recently updated"),
            ("name", "Name"),
            ("status", "Status"),
        )
    )

    rows = []
    for program in programs:
        attention = program_attention_state(program)
        attention_class = "ok" if attention == "OK" else "attention"
        rows.append(
            f"""
            <tr>
              <td><a href="/programs/{program.id}/view">{escape(program.name)}</a></td>
              <td>{escape(program.description or "")}</td>
              <td><span class="pill" style="background:{escape(program.program_status.color)}1a;color:{escape(program.program_status.color)}">{escape(program.program_status.name)}</span></td>
              <td><span class="pill {attention_class}">{escape(attention)}</span></td>
              <td>{escape(_format_datetime(program.updated_at))}</td>
              <td class="row-actions">
                <details class="action-menu">
                  <summary class="button secondary">Actions</summary>
                  <div class="menu">
                    <a href="/programs/{program.id}/edit">Edit</a>
                    <a href="/programs/{program.id}/delete/confirm">Delete</a>
                  </div>
                </details>
              </td>
            </tr>
            """
        )
    table_rows = "".join(rows) or """
      <tr>
        <td colspan="6" class="muted">No programs match the current view.</td>
      </tr>
    """

    body = f"""
    <header>
      <div>
        <h1>TPM Cockpit</h1>
        <div class="muted">Programs workspace</div>
      </div>
      <div class="top-links">
        <a href="/settings">Settings</a>
        <a href="/docs">API docs</a>
      </div>
    </header>
    <div class="layout">
      <section class="panel">
        <h2>New Program</h2>
        <form method="post" action="/programs/create">
          <label for="name">Name</label>
          <input id="name" name="name" required maxlength="200">
          <label for="description">Description</label>
          <textarea id="description" name="description"></textarea>
          <label for="status">Status</label>
          <select id="status" name="status">
            {_program_status_options(all_statuses)}
          </select>
          <div class="actions">
            <button type="submit">Create Program</button>
          </div>
        </form>
      </section>
      <section class="panel">
        <h2>Program List</h2>
        <form class="filters" method="get" action="/">
          <div>
            <label for="status_filter">Status</label>
            <select id="status_filter" name="status_filter">{status_options}</select>
          </div>
          <div>
            <label for="attention_filter">Attention</label>
            <select id="attention_filter" name="attention_filter">{attention_options}</select>
          </div>
          <div>
            <label for="sort">Sort</label>
            <select id="sort" name="sort">{sort_options}</select>
          </div>
          <div class="actions">
            <button type="submit">Apply</button>
            <a class="button secondary" href="/">Clear</a>
          </div>
        </form>
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Description</th>
              <th>Status</th>
              <th>Attention</th>
              <th>Updated</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>{table_rows}</tbody>
        </table>
      </section>
    </div>
    """
    return _page_shell("Programs", body)


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
def edit_program_page(program_id: int, db: Session = Depends(get_db)) -> str:
    program = db.get(Program, program_id)
    if program is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")
    all_statuses = list(
        db.scalars(select(ProgramStatus).order_by(ProgramStatus.sort_order.asc(), ProgramStatus.id.asc()))
    )
    status_options = _program_status_options(all_statuses, selected_slug=program.status)
    body = f"""
    <header>
      <div>
        <h1>Edit Program</h1>
        <div class="muted">{escape(program.name)}</div>
      </div>
      <a href="/">Back to Programs</a>
    </header>
    <section class="panel">
      <form method="post" action="/programs/{program.id}/update">
        <label for="name">Name</label>
        <input id="name" name="name" required maxlength="200" value="{escape(program.name)}">
        <label for="description">Description</label>
        <textarea id="description" name="description">{escape(program.description or "")}</textarea>
        <label for="status">Status</label>
        <select id="status" name="status">{status_options}</select>
        <div class="actions">
          <button type="submit">Save Program</button>
          <a class="button secondary" href="/">Cancel</a>
        </div>
      </form>
    </section>
    """
    return _page_shell("Edit Program", body)


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
def confirm_delete_program_page(program_id: int, db: Session = Depends(get_db)) -> str:
    program = db.get(Program, program_id)
    if program is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")
    body = f"""
    <header>
      <div>
        <h1>Delete Program?</h1>
        <div class="muted">{escape(program.name)}</div>
      </div>
      <a href="/">Back to Programs</a>
    </header>
    <section class="panel">
      <p>Deleting this Program will also delete its Work Items.</p>
      <form method="post" action="/programs/{program.id}/delete">
        <div class="actions">
          <button class="danger" type="submit">Confirm Delete</button>
          <a class="button secondary" href="/">Cancel</a>
        </div>
      </form>
    </section>
    """
    return _page_shell("Delete Program", body)


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
) -> str:
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

    attention = program_attention_state(program)
    attention_class = "ok" if attention == "OK" else "attention"
    work_item_status_options = "".join(
        _select_option(work_status, work_status.replace("_", " ").title(), None)
        for work_status in WORK_ITEM_STATUSES
    )
    work_item_priority_options = "".join(
        _select_option(priority, priority.title(), "medium")
        for priority in WORK_ITEM_PRIORITIES
    )
    priority_filter_options = '<option value="">All priorities</option>' + "".join(
        _select_option(priority, priority.title(), priority_filter)
        for priority in WORK_ITEM_PRIORITIES
    )
    stale_filter_options = (
        '<option value="">All touch states</option>'
        + _select_option("stale", "Stale", stale_filter)
        + _select_option("not_stale", "Not stale", stale_filter)
    )
    owner_options = '<option value="">All owners</option>' + "".join(
        _select_option(owner, owner, owner_filter)
        for owner in sorted({item.owner for item in program.work_items if item.owner})
    )
    source_filter_options = '<option value="">All sources</option>' + "".join(
        _select_option(str(source_type.id), source_type.name, source_type_filter)
        for source_type in source_types
    )
    sort_options = "".join(
        _select_option(value, label, work_sort)
        for value, label in WORK_ITEM_SORT_LABELS.items()
    )
    dependency_type_options = "".join(
        _select_option(value, value.replace("_", " ").title(), None)
        for value in DEPENDENCY_TYPES
    )
    dependency_status_options = "".join(
        _select_option(value, value.replace("_", " ").title(), None)
        for value in DEPENDENCY_STATUSES
    )
    blocking_level_options = "".join(
        _select_option(value, value.title(), "medium")
        for value in BLOCKING_LEVELS
    )
    dependency_status_filter_options = '<option value="">All statuses</option>' + "".join(
        _select_option(value, value.replace("_", " ").title(), dependency_status_filter)
        for value in DEPENDENCY_STATUSES
    )
    dependency_type_filter_options = '<option value="">All types</option>' + "".join(
        _select_option(value, value.replace("_", " ").title(), dependency_type_filter)
        for value in DEPENDENCY_TYPES
    )
    blocking_level_filter_options = '<option value="">All levels</option>' + "".join(
        _select_option(value, value.title(), blocking_level_filter)
        for value in BLOCKING_LEVELS
    )
    dependency_owner_options = '<option value="">All owners</option>' + "".join(
        _select_option(owner, owner, dependency_owner_filter)
        for owner in sorted({item.owner for item in program.dependencies if item.owner})
    )
    dependency_sort_options = "".join(
        _select_option(value, label, dependency_sort)
        for value, label in DEPENDENCY_SORT_LABELS.items()
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

    rows = []
    for work_item in work_items:
        blocked = work_item.status == "blocked"
        overdue = work_item_is_overdue(work_item)
        stale = work_item_is_stale(work_item)
        row_class = "blocked-row" if blocked else "overdue-row" if overdue else "stale-row" if stale else ""
        source_name = work_item.source_type.name if work_item.source_type else ""
        link_html = (
            f'<a href="{escape(work_item.link)}" target="_blank" rel="noreferrer">Open</a>'
            if work_item.link
            else ""
        )
        due_html = escape(_format_date(work_item.due_date))
        if overdue:
            due_html += ' <span class="pill attention">Overdue</span>'
        next_step_html = escape(work_item.next_step or "")
        signal_pills = []
        if stale:
            signal_pills.append('<span class="pill attention">Stale</span>')
        if work_item.last_touched_at:
            signal_pills.append(f'<span class="pill">Touched {_format_datetime(work_item.last_touched_at)}</span>')
        signals_html = " ".join(signal_pills)
        rows.append(
            f"""
            <tr class="{row_class}">
              <td>{escape(work_item.title)}</td>
              <td><span class="pill">{escape(work_item.status)}</span></td>
              <td><span class="pill">{escape(work_item.priority)}</span></td>
              <td>{escape(work_item.owner or "")}</td>
              <td>{next_step_html} {signals_html}</td>
              <td>{escape(source_name)}</td>
              <td>{due_html}</td>
              <td>{link_html}</td>
              <td>{escape(_format_datetime(work_item.updated_at))}</td>
              <td class="row-actions">
                <details class="action-menu">
                  <summary class="button secondary">Actions</summary>
                  <div class="menu">
                    <a href="/programs/{program.id}/view?edit_work_item_id={work_item.id}#edit-work-item">Edit</a>
                    <form method="post" action="/work-items/{work_item.id}/touch">
                      <button type="submit">Mark touched</button>
                    </form>
                    <a href="/work-items/{work_item.id}/delete/confirm">Delete</a>
                  </div>
                </details>
              </td>
            </tr>
            """
        )
    work_rows = "".join(rows) or """
      <tr>
        <td colspan="10" class="muted">No work items match the current view.</td>
      </tr>
    """
    new_work_item_open = " open" if show_new_work_item == "1" or work_item_error else ""
    error_html = f'<div class="error">{escape(work_item_error)}</div>' if work_item_error else ""
    edit_panel = ""
    if edit_work_item is not None:
        edit_status_options = "".join(
            _select_option(work_status, work_status.replace("_", " ").title(), edit_work_item.status)
            for work_status in WORK_ITEM_STATUSES
        )
        edit_priority_options = "".join(
            _select_option(priority, priority.title(), edit_work_item.priority)
            for priority in WORK_ITEM_PRIORITIES
        )
        edit_panel = f"""
        <details id="edit-work-item" class="collapsible-panel" open>
          <summary class="button secondary">Edit Work Item</summary>
          <div class="collapsible-body">
            <form method="post" action="/work-items/{edit_work_item.id}/update">
              <label for="edit-title">Title</label>
              <input id="edit-title" name="title" required maxlength="200" value="{escape(edit_work_item.title)}">
              <label for="edit-description">Description</label>
              <textarea id="edit-description" name="description">{escape(edit_work_item.description or "")}</textarea>
              <div class="compact-fields">
                <div>
                  <label for="edit-status">Status</label>
                  <select id="edit-status" name="status">{edit_status_options}</select>
                </div>
                <div>
                  <label for="edit-priority">Priority</label>
                  <select id="edit-priority" name="priority">{edit_priority_options}</select>
                </div>
                <div>
                  <label for="edit-owner">Owner</label>
                  <input id="edit-owner" name="owner" maxlength="120" value="{escape(edit_work_item.owner or "")}">
                </div>
                <div>
                  <label for="edit-next-step">Next Step</label>
                  <input id="edit-next-step" name="next_step" value="{escape(edit_work_item.next_step or "")}">
                </div>
                <div>
                  <label for="edit-source-type-id">Source Type</label>
                  <select id="edit-source-type-id" name="source_type_id">{_source_type_options(source_types, edit_work_item.source_type_id)}</select>
                </div>
                <div>
                  <label for="edit-due-date">Due Date</label>
                  <input id="edit-due-date" name="due_date" type="date" value="{escape(_format_date(edit_work_item.due_date))}">
                </div>
                <div>
                  <label for="edit-link">Link</label>
                  <input id="edit-link" name="link" maxlength="500" value="{escape(edit_work_item.link or "")}">
                </div>
              </div>
              <div class="actions">
                <button type="submit">Save Work Item</button>
                <a class="button secondary" href="/programs/{program.id}/view">Cancel</a>
              </div>
            </form>
          </div>
        </details>
        """

    dependency_rows = []
    for dependency in dependencies:
        blocked = dependency.status == "blocked"
        critical = dependency.blocking_level == "critical"
        stale_dependency = dependency_is_stale(dependency)
        dependency_row_class = (
            "blocked-row" if blocked else "critical-row" if critical else "stale-row" if stale_dependency else ""
        )
        dependency_signals = []
        if blocked:
            dependency_signals.append('<span class="pill attention">Blocked</span>')
        if critical:
            dependency_signals.append('<span class="pill attention">Critical</span>')
        if stale_dependency:
            dependency_signals.append('<span class="pill attention">Stale</span>')
        dependency_signal_html = " ".join(dependency_signals)
        dependency_rows.append(
            f"""
            <tr class="{dependency_row_class}">
              <td>{escape(dependency.title)} {dependency_signal_html}</td>
              <td><span class="pill">{escape(dependency.status)}</span></td>
              <td>{escape(dependency.dependency_type)}</td>
              <td><span class="pill">{escape(dependency.blocking_level)}</span></td>
              <td>{escape(dependency.owner or "")}</td>
              <td>{escape(dependency.external_team or "")}</td>
              <td>{escape(_format_date(dependency.due_date))}</td>
              <td>{escape(_format_datetime(dependency.last_confirmation_at))}</td>
              <td>{escape(_format_datetime(dependency.updated_at))}</td>
              <td class="row-actions">
                <details class="action-menu">
                  <summary class="button secondary">Actions</summary>
                  <div class="menu">
                    <a href="/programs/{program.id}/view?edit_dependency_id={dependency.id}#edit-dependency">Edit</a>
                    <form method="post" action="/dependencies/{dependency.id}/confirm-ui">
                      <button type="submit">Confirm Dependency</button>
                    </form>
                    <a href="/dependencies/{dependency.id}/delete/confirm">Delete</a>
                  </div>
                </details>
              </td>
            </tr>
            """
        )
    dependency_table_rows = "".join(dependency_rows) or """
      <tr>
        <td colspan="10" class="muted">No dependencies match the current view.</td>
      </tr>
    """
    new_dependency_open = " open" if show_new_dependency == "1" or dependency_error else ""
    dependency_error_html = f'<div class="error">{escape(dependency_error)}</div>' if dependency_error else ""
    edit_dependency_panel = ""
    if edit_dependency is not None:
        edit_dependency_type_options = "".join(
            _select_option(value, value.replace("_", " ").title(), edit_dependency.dependency_type)
            for value in DEPENDENCY_TYPES
        )
        edit_dependency_status_options = "".join(
            _select_option(value, value.replace("_", " ").title(), edit_dependency.status)
            for value in DEPENDENCY_STATUSES
        )
        edit_blocking_level_options = "".join(
            _select_option(value, value.title(), edit_dependency.blocking_level)
            for value in BLOCKING_LEVELS
        )
        edit_dependency_panel = f"""
        <details id="edit-dependency" class="collapsible-panel" open>
          <summary class="button secondary">Edit Dependency</summary>
          <div class="collapsible-body">
            <form method="post" action="/dependencies/{edit_dependency.id}/update">
              <label for="edit-dependency-title">Title</label>
              <input id="edit-dependency-title" name="title" required maxlength="200" value="{escape(edit_dependency.title)}">
              <label for="edit-dependency-description">Description</label>
              <textarea id="edit-dependency-description" name="description">{escape(edit_dependency.description or "")}</textarea>
              <div class="compact-fields">
                <div>
                  <label for="edit-dependency-type">Type</label>
                  <select id="edit-dependency-type" name="dependency_type">{edit_dependency_type_options}</select>
                </div>
                <div>
                  <label for="edit-dependency-status">Status</label>
                  <select id="edit-dependency-status" name="status">{edit_dependency_status_options}</select>
                </div>
                <div>
                  <label for="edit-blocking-level">Blocking Level</label>
                  <select id="edit-blocking-level" name="blocking_level">{edit_blocking_level_options}</select>
                </div>
                <div>
                  <label for="edit-dependency-owner">Owner</label>
                  <input id="edit-dependency-owner" name="owner" maxlength="120" value="{escape(edit_dependency.owner or "")}">
                </div>
                <div>
                  <label for="edit-external-team">External Team</label>
                  <input id="edit-external-team" name="external_team" maxlength="120" value="{escape(edit_dependency.external_team or "")}">
                </div>
                <div>
                  <label for="edit-dependency-due-date">Due Date</label>
                  <input id="edit-dependency-due-date" name="due_date" type="date" value="{escape(_format_date(edit_dependency.due_date))}">
                </div>
                <div>
                  <label for="edit-last-confirmation-at">Last Confirmation</label>
                  <input id="edit-last-confirmation-at" name="last_confirmation_at" type="datetime-local" value="{escape(edit_dependency.last_confirmation_at.strftime('%Y-%m-%dT%H:%M') if edit_dependency.last_confirmation_at else '')}">
                </div>
              </div>
              <label for="edit-dependency-notes">Notes</label>
              <textarea id="edit-dependency-notes" name="notes">{escape(edit_dependency.notes or "")}</textarea>
              <div class="actions">
                <button type="submit">Save Dependency</button>
                <a class="button secondary" href="/programs/{program.id}/view">Cancel</a>
              </div>
            </form>
          </div>
        </details>
        """

    placeholder_sections = "".join(
        f"""
        <section class="panel placeholder">
          <h3>{title}</h3>
          <div class="muted">Not implemented yet.</div>
        </section>
        """
        for title in ("Risks", "Decisions", "Notes")
    )
    body = f"""
    <header>
      <div>
        <h1>{escape(program.name)}</h1>
        <div class="muted">Program detail</div>
      </div>
      <div class="top-links">
        <a href="/">Back to Programs</a>
        <a href="/settings">Settings</a>
      </div>
    </header>
    <section class="panel">
      <h2>Overview</h2>
      <p>{escape(program.description or "No description yet.")}</p>
      <div class="detail-grid">
        <div><strong>Status</strong><br><span class="pill">{escape(program.status)}</span></div>
        <div><strong>Attention</strong><br><span class="pill {attention_class}">{escape(attention)}</span></div>
        <div><strong>Created</strong><br>{escape(_format_datetime(program.created_at))}</div>
        <div><strong>Updated</strong><br>{escape(_format_datetime(program.updated_at))}</div>
      </div>
    </section>
    <section class="panel">
      <div style="display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap;">
        <h2>Work Items</h2>
      </div>
      <details id="new-work-item" class="collapsible-panel"{new_work_item_open}>
        <summary class="button">New Work Item</summary>
        <div class="collapsible-body">
          {error_html}
          <form method="post" action="/programs/{program.id}/work-items/create">
            <label for="work-title">Title</label>
            <input id="work-title" name="title" required maxlength="200">
            <label for="work-description">Description</label>
            <textarea id="work-description" name="description"></textarea>
            <div class="compact-fields">
              <div>
                <label for="work-status">Status</label>
                <select id="work-status" name="status">{work_item_status_options}</select>
              </div>
              <div>
                <label for="work-priority">Priority</label>
                <select id="work-priority" name="priority">{work_item_priority_options}</select>
              </div>
              <div>
                <label for="work-owner">Owner</label>
                <input id="work-owner" name="owner" maxlength="120">
              </div>
              <div>
                <label for="work-next-step">Next Step</label>
                <input id="work-next-step" name="next_step">
              </div>
              <div>
                <label for="work-source-type">Source Type</label>
                <select id="work-source-type" name="source_type_id">{_source_type_options(source_types)}</select>
              </div>
              <div>
                <label for="work-due-date">Due Date</label>
                <input id="work-due-date" name="due_date" type="date">
              </div>
              <div>
                <label for="work-link">Link</label>
                <input id="work-link" name="link" maxlength="500">
              </div>
            </div>
            <div class="actions">
              <button type="submit">Create Work Item</button>
            </div>
          </form>
        </div>
      </details>
      {edit_panel}
      <form class="filters" method="get" action="/programs/{program.id}/view">
        <div>
          <label for="work_status_filter">Status</label>
          <select id="work_status_filter" name="work_status_filter">
            <option value="">All statuses</option>
            {''.join(_select_option(work_status, work_status.replace("_", " ").title(), work_status_filter) for work_status in WORK_ITEM_STATUSES)}
          </select>
        </div>
        <div>
          <label for="priority_filter">Priority</label>
          <select id="priority_filter" name="priority_filter">{priority_filter_options}</select>
        </div>
        <div>
          <label for="stale_filter">Stale</label>
          <select id="stale_filter" name="stale_filter">{stale_filter_options}</select>
        </div>
        <div>
          <label for="owner_filter">Owner</label>
          <select id="owner_filter" name="owner_filter">{owner_options}</select>
        </div>
        <div>
          <label for="source_type_filter">Source Type</label>
          <select id="source_type_filter" name="source_type_filter">{source_filter_options}</select>
        </div>
        <div>
          <label for="work_sort">Sort</label>
          <select id="work_sort" name="work_sort">{sort_options}</select>
        </div>
        <div class="actions">
          <button type="submit">Apply</button>
          <a class="button secondary" href="/programs/{program.id}/view">Clear</a>
        </div>
      </form>
      <table>
        <thead>
          <tr>
            <th>Title</th>
            <th>Status</th>
            <th>Priority</th>
            <th>Owner</th>
            <th>Next Step</th>
            <th>Source Type</th>
            <th>Due Date</th>
            <th>Link</th>
            <th>Updated</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>{work_rows}</tbody>
      </table>
    </section>
    <section class="panel">
      <div style="display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap;">
        <h2>Dependencies</h2>
      </div>
      <details id="new-dependency" class="collapsible-panel"{new_dependency_open}>
        <summary class="button">New Dependency</summary>
        <div class="collapsible-body">
          {dependency_error_html}
          <form method="post" action="/programs/{program.id}/dependencies/create">
            <label for="dependency-title">Title</label>
            <input id="dependency-title" name="title" required maxlength="200">
            <label for="dependency-description">Description</label>
            <textarea id="dependency-description" name="description"></textarea>
            <div class="compact-fields">
              <div>
                <label for="dependency-type">Type</label>
                <select id="dependency-type" name="dependency_type">{dependency_type_options}</select>
              </div>
              <div>
                <label for="dependency-status">Status</label>
                <select id="dependency-status" name="status">{dependency_status_options}</select>
              </div>
              <div>
                <label for="blocking-level">Blocking Level</label>
                <select id="blocking-level" name="blocking_level">{blocking_level_options}</select>
              </div>
              <div>
                <label for="dependency-owner">Owner</label>
                <input id="dependency-owner" name="owner" maxlength="120">
              </div>
              <div>
                <label for="external-team">External Team</label>
                <input id="external-team" name="external_team" maxlength="120">
              </div>
              <div>
                <label for="dependency-due-date">Due Date</label>
                <input id="dependency-due-date" name="due_date" type="date">
              </div>
              <div>
                <label for="last-confirmation-at">Last Confirmation</label>
                <input id="last-confirmation-at" name="last_confirmation_at" type="datetime-local">
              </div>
            </div>
            <label for="dependency-notes">Notes</label>
            <textarea id="dependency-notes" name="notes"></textarea>
            <div class="actions">
              <button type="submit">Create Dependency</button>
            </div>
          </form>
        </div>
      </details>
      {edit_dependency_panel}
      <form class="filters" method="get" action="/programs/{program.id}/view">
        <div>
          <label for="dependency_status_filter">Status</label>
          <select id="dependency_status_filter" name="dependency_status_filter">{dependency_status_filter_options}</select>
        </div>
        <div>
          <label for="dependency_type_filter">Type</label>
          <select id="dependency_type_filter" name="dependency_type_filter">{dependency_type_filter_options}</select>
        </div>
        <div>
          <label for="blocking_level_filter">Blocking Level</label>
          <select id="blocking_level_filter" name="blocking_level_filter">{blocking_level_filter_options}</select>
        </div>
        <div>
          <label for="dependency_owner_filter">Owner</label>
          <select id="dependency_owner_filter" name="dependency_owner_filter">{dependency_owner_options}</select>
        </div>
        <div>
          <label for="dependency_sort">Sort</label>
          <select id="dependency_sort" name="dependency_sort">{dependency_sort_options}</select>
        </div>
        <div class="actions">
          <button type="submit">Apply</button>
          <a class="button secondary" href="/programs/{program.id}/view">Clear</a>
        </div>
      </form>
      <table>
        <thead>
          <tr>
            <th>Title</th>
            <th>Status</th>
            <th>Type</th>
            <th>Blocking</th>
            <th>Owner</th>
            <th>External Team</th>
            <th>Due Date</th>
            <th>Confirmed</th>
            <th>Updated</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>{dependency_table_rows}</tbody>
      </table>
    </section>
    <div class="placeholder-grid">
      {placeholder_sections}
    </div>
    """
    return _page_shell(program.name, body)


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
def confirm_delete_work_item_page(work_item_id: int, db: Session = Depends(get_db)) -> str:
    work_item = db.get(WorkItem, work_item_id)
    if work_item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work item not found")
    body = f"""
    <header>
      <div>
        <h1>Delete Work Item?</h1>
        <div class="muted">{escape(work_item.title)}</div>
      </div>
      <a href="/programs/{work_item.program_id}/view">Back to Program</a>
    </header>
    <section class="panel">
      <p>This removes the Work Item from the Program.</p>
      <form method="post" action="/work-items/{work_item.id}/delete">
        <div class="actions">
          <button class="danger" type="submit">Confirm Delete</button>
          <a class="button secondary" href="/programs/{work_item.program_id}/view">Cancel</a>
        </div>
      </form>
    </section>
    """
    return _page_shell("Delete Work Item", body)


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
def confirm_delete_dependency_page(dependency_id: int, db: Session = Depends(get_db)) -> str:
    dependency = db.get(Dependency, dependency_id)
    if dependency is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dependency not found")
    body = f"""
    <header>
      <div>
        <h1>Delete Dependency?</h1>
        <div class="muted">{escape(dependency.title)}</div>
      </div>
      <a href="/programs/{dependency.program_id}/view">Back to Program</a>
    </header>
    <section class="panel">
      <p>This removes the Dependency from the Program.</p>
      <form method="post" action="/dependencies/{dependency.id}/delete">
        <div class="actions">
          <button class="danger" type="submit">Confirm Delete</button>
          <a class="button secondary" href="/programs/{dependency.program_id}/view">Cancel</a>
        </div>
      </form>
    </section>
    """
    return _page_shell("Delete Dependency", body)


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
    edit_status_id: Optional[int] = None,
    edit_source_type_id: Optional[int] = None,
    db: Session = Depends(get_db),
) -> str:
    seed_default_program_statuses(db)

    # ── Program Statuses section ──────────────────────────────────────────────
    all_statuses = list(
        db.scalars(select(ProgramStatus).order_by(ProgramStatus.sort_order.asc(), ProgramStatus.id.asc()))
    )
    status_rows = []
    for ps in all_statuses:
        is_editing = edit_status_id == ps.id
        color_swatch = f'<span style="display:inline-block;width:14px;height:14px;border-radius:3px;background:{escape(ps.color)};vertical-align:middle;margin-right:6px"></span>'
        default_badge = ' <span class="pill">Default</span>' if ps.is_default else ""

        if is_editing:
            status_rows.append(f"""
            <tr data-id="{ps.id}">
              <td></td>
              <td colspan="5">
                <form method="post" action="/settings/program-statuses/{ps.id}/update" style="display:flex;gap:8px;align-items:flex-end;padding:4px 0;flex-wrap:wrap">
                  <div>
                    <label for="edit_name_{ps.id}" style="margin:0 0 4px">Name</label>
                    <input id="edit_name_{ps.id}" name="name" value="{escape(ps.name)}" required maxlength="120">
                  </div>
                  <div>
                    <label for="edit_slug_{ps.id}" style="margin:0 0 4px">Slug</label>
                    <input id="edit_slug_{ps.id}" name="slug" value="{escape(ps.slug)}" required maxlength="50">
                  </div>
                  <div>
                    <label for="edit_color_{ps.id}" style="margin:0 0 4px">Color</label>
                    <input id="edit_color_{ps.id}" name="color" type="color" value="{escape(ps.color)}">
                  </div>
                  <div>
                    <label style="margin:0 0 4px">Default</label>
                    <select name="is_default">
                      {_select_option("1", "Yes", "1" if ps.is_default else "0")}
                      {_select_option("0", "No", "0" if not ps.is_default else "1")}
                    </select>
                  </div>
                  <div class="actions" style="margin:0">
                    <button type="submit">Save</button>
                    <a class="button secondary" href="/settings#program-statuses">Cancel</a>
                  </div>
                </form>
              </td>
            </tr>""")
        else:
            status_rows.append(f"""
            <tr draggable="true" data-id="{ps.id}">
              <td class="drag-handle">⠿</td>
              <td>{color_swatch}{escape(ps.name)}{default_badge}</td>
              <td><code style="font-size:12px">{escape(ps.slug)}</code></td>
              <td>{escape(ps.color)}</td>
              <td>{"✓" if ps.is_default else "—"}</td>
              <td>
                <div style="display:flex;gap:6px;flex-wrap:wrap">
                  <a class="button secondary" href="/settings?edit_status_id={ps.id}#program-statuses">Edit</a>
                  <form method="post" action="/settings/program-statuses/{ps.id}/delete" style="display:inline">
                    <button class="secondary" type="submit">Delete</button>
                  </form>
                </div>
              </td>
            </tr>""")

    status_table_body = "".join(status_rows) or '<tr><td colspan="6" class="muted">No program statuses yet.</td></tr>'

    # ── Source Types section ──────────────────────────────────────────────────
    source_types = list(
        db.scalars(select(SourceType).order_by(SourceType.sort_order.asc(), SourceType.id.asc()))
    )
    source_rows = []
    for source_type in source_types:
        is_editing_st = edit_source_type_id == source_type.id
        if is_editing_st:
            source_rows.append(f"""
            <tr data-id="{source_type.id}">
              <td></td>
              <td colspan="3">
                <form method="post" action="/settings/source-types/{source_type.id}/update" style="display:flex;gap:8px;align-items:flex-end;padding:4px 0;flex-wrap:wrap">
                  <div>
                    <label for="edit_st_name_{source_type.id}" style="margin:0 0 4px">Name</label>
                    <input id="edit_st_name_{source_type.id}" name="name" value="{escape(source_type.name)}" required maxlength="120">
                  </div>
                  <div class="actions" style="margin:0">
                    <button type="submit">Save</button>
                    <a class="button secondary" href="/settings#source-types">Cancel</a>
                  </div>
                </form>
              </td>
            </tr>""")
        else:
            source_rows.append(f"""
            <tr draggable="true" data-id="{source_type.id}">
              <td class="drag-handle">⠿</td>
              <td>{escape(source_type.name)}</td>
              <td><code style="font-size:12px">{escape(source_type.slug)}</code></td>
              <td>
                <div style="display:flex;gap:6px;flex-wrap:wrap">
                  <a class="button secondary" href="/settings?edit_source_type_id={source_type.id}#source-types">Edit</a>
                  <form method="post" action="/settings/source-types/{source_type.id}/delete" style="display:inline">
                    <button class="secondary" type="submit">Delete</button>
                  </form>
                </div>
              </td>
            </tr>""")

    source_table_body = "".join(source_rows) or '<tr><td colspan="4" class="muted">No source types yet.</td></tr>'

    body = f"""
    <header>
      <div>
        <h1>Settings</h1>
        <div class="muted">Workspace configuration</div>
      </div>
      <a href="/">Back to Programs</a>
    </header>

    <nav class="settings-nav">
      <a href="#program-statuses">Program Statuses</a>
      <a href="#source-types">Source Types</a>
    </nav>

    <div class="settings-section" id="program-statuses">
      <div class="settings-section-header">
        <h2>Program Statuses</h2>
        <details class="create-panel">
          <summary class="button secondary">+ New Program Status</summary>
          <div class="panel">
            <form method="post" action="/settings/program-statuses/create">
              <label for="ps_name">Name</label>
              <input id="ps_name" name="name" required maxlength="120">
              <label for="ps_slug">Slug</label>
              <input id="ps_slug" name="slug" required maxlength="50" placeholder="e.g. on-hold">
              <label for="ps_color">Color</label>
              <input id="ps_color" name="color" type="color" value="#6b7280">
              <div class="actions">
                <button type="submit">Create Status</button>
              </div>
            </form>
          </div>
        </details>
      </div>
      <table id="tbl-program-statuses">
        <thead>
          <tr>
            <th></th><th>Name</th><th>Slug</th><th>Color</th><th>Default</th><th>Actions</th>
          </tr>
        </thead>
        <tbody>{status_table_body}</tbody>
      </table>
    </div>

    <div class="settings-section" id="source-types">
      <div class="settings-section-header">
        <h2>Source Types</h2>
        <details class="create-panel">
          <summary class="button secondary">+ New Source Type</summary>
          <div class="panel">
            <form method="post" action="/settings/source-types/create">
              <label for="st_name">Name</label>
              <input id="st_name" name="name" required maxlength="120">
              <label for="st_slug">Slug</label>
              <input id="st_slug" name="slug" maxlength="50" placeholder="e.g. email-thread">
              <div class="actions">
                <button type="submit">Create Source Type</button>
              </div>
            </form>
          </div>
        </details>
      </div>
      <table id="tbl-source-types">
        <thead>
          <tr>
            <th></th><th>Name</th><th>Slug</th><th>Actions</th>
          </tr>
        </thead>
        <tbody>{source_table_body}</tbody>
      </table>
    </div>
    <script>
    (function() {{
      function initDragSort(tableId, reorderUrl) {{
        var tbody = document.querySelector('#' + tableId + ' tbody');
        if (!tbody) return;
        var dragging = null;
        tbody.addEventListener('dragstart', function(e) {{
          dragging = e.target.closest('tr[data-id]');
          if (dragging) setTimeout(function() {{ dragging.style.opacity = '0.4'; }}, 0);
        }});
        tbody.addEventListener('dragend', function() {{
          if (dragging) dragging.style.opacity = '';
          dragging = null;
        }});
        tbody.addEventListener('dragover', function(e) {{
          e.preventDefault();
          if (!dragging) return;
          var row = e.target.closest('tr[data-id]');
          if (row && row !== dragging) {{
            var mid = row.getBoundingClientRect().top + row.getBoundingClientRect().height / 2;
            if (e.clientY < mid) tbody.insertBefore(dragging, row);
            else tbody.insertBefore(dragging, row.nextSibling);
          }}
        }});
        tbody.addEventListener('drop', function(e) {{
          e.preventDefault();
          var ids = [].slice.call(tbody.querySelectorAll('tr[data-id]')).map(function(r) {{ return +r.dataset.id; }});
          fetch(reorderUrl, {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{ids:ids}})}});
        }});
      }}
      initDragSort('tbl-program-statuses', '/settings/program-statuses/reorder');
      initDragSort('tbl-source-types', '/settings/source-types/reorder');
    }})();
    </script>
    """
    return _page_shell("Settings", body)


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
            # Reject slug change if it conflicts with another status
            slug_conflict = db.scalar(
                select(ProgramStatus).where(ProgramStatus.slug == slug, ProgramStatus.id != status_id)
            )
            if slug_conflict is None:
                ps.slug = slug
            if is_default:
                # Ensure exactly one default
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
        # Can't delete the last status — programs would have no valid status
        return RedirectResponse("/settings#program-statuses", status_code=status.HTTP_303_SEE_OTHER)

    if ps.is_default:
        replacement.is_default = True

    # Reassign programs via ORM so the session stays consistent
    for prog in list(db.scalars(select(Program).where(Program.status_id == status_id))):
        prog.status_id = replacement.id

    # Flush reassignments before issuing the DELETE so the FK is clear
    db.flush()
    db.delete(ps)
    db.commit()
    return RedirectResponse("/settings#program-statuses", status_code=status.HTTP_303_SEE_OTHER)
