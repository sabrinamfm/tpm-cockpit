from datetime import date
from html import escape
from typing import Optional
from urllib.parse import parse_qs, urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.domain.programs import program_attention_state, work_item_is_overdue
from app.models import Program, SourceType, WorkItem

router = APIRouter(tags=["ui"])

PROGRAM_STATUSES = ("active", "paused", "completed", "archived")
WORK_ITEM_STATUSES = ("open", "in_progress", "blocked", "completed", "cancelled")
ATTENTION_STATES = ("Needs attention", "OK")
PROGRAM_SORTS = {
    "name": Program.name.asc(),
    "status": Program.status.asc(),
    "updated_at": Program.updated_at.desc(),
}
WORK_ITEM_SORT_LABELS = {
    "title": "Title",
    "status": "Status",
    "owner": "Owner",
    "source_type": "Source Type",
    "due_date": "Due Date",
    "updated_at": "Updated",
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
    .menu a {{ display: block; padding: 7px 8px; border-radius: 6px; }}
    .menu a:hover {{ background: #f2f5f9; text-decoration: none; }}
    .pill {{ display: inline-block; border-radius: 999px; padding: 3px 8px; font-size: 12px; font-weight: 700; background: #eef2f7; color: #344054; }}
    .attention {{ background: #fff3cd; color: #7a4d00; }}
    .ok {{ background: #e7f5ec; color: #246b3d; }}
    .blocked-row {{ background: #fff4f3; }}
    .overdue-row {{ background: #fff7ed; }}
    .detail-grid {{ display: grid; grid-template-columns: repeat(2, minmax(180px, 1fr)); gap: 12px; margin: 16px 0; }}
    .placeholder-grid {{ display: grid; grid-template-columns: repeat(2, minmax(220px, 1fr)); gap: 14px; }}
    .placeholder {{ min-height: 86px; }}
    .compact-fields {{ display: grid; grid-template-columns: repeat(3, minmax(120px, 1fr)); gap: 8px; }}
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
    if status_filter and status_filter not in PROGRAM_STATUSES:
        status_filter = None
    if attention_filter and attention_filter not in ATTENTION_STATES:
        attention_filter = None
    if sort not in PROGRAM_SORTS:
        sort = "updated_at"

    statement = select(Program).options(selectinload(Program.work_items))
    if status_filter:
        statement = statement.where(Program.status == status_filter)
    statement = statement.order_by(PROGRAM_SORTS[sort], Program.id.desc())
    programs = list(db.scalars(statement))
    if attention_filter:
        programs = [
            program for program in programs if program_attention_state(program) == attention_filter
        ]

    status_options = '<option value="">All statuses</option>' + "".join(
        _select_option(program_status, program_status.title(), status_filter)
        for program_status in PROGRAM_STATUSES
    )
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
              <td><span class="pill">{escape(program.status)}</span></td>
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
        <a href="/settings/source-types">Settings</a>
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
            {_select_option("active", "Active", "active")}
            {_select_option("paused", "Paused", None)}
            {_select_option("completed", "Completed", None)}
            {_select_option("archived", "Archived", None)}
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
    program_status = parsed.get("status", "active")
    if not name or program_status not in PROGRAM_STATUSES:
        return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)

    db.add(Program(name=name, description=description, status=program_status))
    db.commit()
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/programs/{program_id}/edit", response_class=HTMLResponse, include_in_schema=False)
def edit_program_page(program_id: int, db: Session = Depends(get_db)) -> str:
    program = db.get(Program, program_id)
    if program is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")
    status_options = "".join(
        _select_option(program_status, program_status.title(), program.status)
        for program_status in PROGRAM_STATUSES
    )
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
    program_status = parsed.get("status", program.status)
    if name and program_status in PROGRAM_STATUSES:
        program.name = name
        program.description = parsed.get("description", "").strip() or None
        program.status = program_status
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


def _parse_optional_int(value: str) -> Optional[int]:
    if not value:
        return None
    return int(value)


def _work_item_sort_key(work_item: WorkItem, sort: str):
    if sort == "title":
        return (work_item.title.lower(), work_item.id)
    if sort == "status":
        return (work_item.status, work_item.id)
    if sort == "owner":
        return ((work_item.owner or "").lower(), work_item.id)
    if sort == "source_type":
        return ((work_item.source_type.name if work_item.source_type else "").lower(), work_item.id)
    if sort == "due_date":
        return (work_item.due_date or date.max, work_item.id)
    return (work_item.updated_at, work_item.id)


@router.get("/programs/{program_id}/view", response_class=HTMLResponse, include_in_schema=False)
def program_detail(
    program_id: int,
    work_status_filter: Optional[str] = None,
    owner_filter: Optional[str] = None,
    source_type_filter: Optional[str] = None,
    work_sort: str = "updated_at",
    db: Session = Depends(get_db),
) -> str:
    program = db.scalars(
        select(Program)
        .options(selectinload(Program.work_items).selectinload(WorkItem.source_type))
        .where(Program.id == program_id)
    ).one_or_none()
    if program is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")
    source_types = list(db.scalars(select(SourceType).order_by(SourceType.name.asc())))

    if work_status_filter and work_status_filter not in WORK_ITEM_STATUSES:
        work_status_filter = None
    if work_sort not in WORK_ITEM_SORT_LABELS:
        work_sort = "updated_at"

    work_items = list(program.work_items)
    if work_status_filter:
        work_items = [item for item in work_items if item.status == work_status_filter]
    if owner_filter:
        work_items = [item for item in work_items if item.owner == owner_filter]
    if source_type_filter:
        source_type_id = int(source_type_filter)
        work_items = [item for item in work_items if item.source_type_id == source_type_id]
    reverse = work_sort == "updated_at"
    work_items = sorted(work_items, key=lambda item: _work_item_sort_key(item, work_sort), reverse=reverse)

    attention = program_attention_state(program)
    attention_class = "ok" if attention == "OK" else "attention"
    work_item_status_options = "".join(
        _select_option(work_status, work_status.replace("_", " ").title(), None)
        for work_status in WORK_ITEM_STATUSES
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

    rows = []
    for work_item in work_items:
        blocked = work_item.status == "blocked"
        overdue = work_item_is_overdue(work_item)
        row_class = "blocked-row" if blocked else "overdue-row" if overdue else ""
        source_name = work_item.source_type.name if work_item.source_type else ""
        link_html = (
            f'<a href="{escape(work_item.link)}" target="_blank" rel="noreferrer">Open</a>'
            if work_item.link
            else ""
        )
        due_html = escape(_format_date(work_item.due_date))
        if overdue:
            due_html += ' <span class="pill attention">Overdue</span>'
        rows.append(
            f"""
            <tr class="{row_class}">
              <td>{escape(work_item.title)}</td>
              <td><span class="pill">{escape(work_item.status)}</span></td>
              <td>{escape(work_item.owner or "")}</td>
              <td>{escape(source_name)}</td>
              <td>{due_html}</td>
              <td>{link_html}</td>
              <td>{escape(_format_datetime(work_item.updated_at))}</td>
              <td class="row-actions">
                <details class="action-menu">
                  <summary class="button secondary">Actions</summary>
                  <div class="menu">
                    <a href="/work-items/{work_item.id}/edit">Edit</a>
                    <a href="/work-items/{work_item.id}/delete/confirm">Delete</a>
                  </div>
                </details>
              </td>
            </tr>
            """
        )
    work_rows = "".join(rows) or """
      <tr>
        <td colspan="8" class="muted">No work items match the current view.</td>
      </tr>
    """

    placeholder_sections = "".join(
        f"""
        <section class="panel placeholder">
          <h3>{title}</h3>
          <div class="muted">Not implemented yet.</div>
        </section>
        """
        for title in ("Risks", "Dependencies", "Decisions", "Notes")
    )
    body = f"""
    <header>
      <div>
        <h1>{escape(program.name)}</h1>
        <div class="muted">Program detail</div>
      </div>
      <div class="top-links">
        <a href="/">Back to Programs</a>
        <a href="/settings/source-types">Settings</a>
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
      <h2>New Work Item</h2>
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
            <label for="work-owner">Owner</label>
            <input id="work-owner" name="owner" maxlength="120">
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
    </section>
    <section class="panel">
      <h2>Work Items</h2>
      <form class="filters" method="get" action="/programs/{program.id}/view">
        <div>
          <label for="work_status_filter">Status</label>
          <select id="work_status_filter" name="work_status_filter">
            <option value="">All statuses</option>
            {''.join(_select_option(work_status, work_status.replace("_", " ").title(), work_status_filter) for work_status in WORK_ITEM_STATUSES)}
          </select>
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
            <th>Owner</th>
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
        return RedirectResponse(f"/programs/{program_id}/view", status_code=status.HTTP_303_SEE_OTHER)

    work_item = WorkItem(
        program_id=program_id,
        title=title,
        description=parsed.get("description", "").strip() or None,
        status=work_status,
        owner=parsed.get("owner", "").strip() or None,
        source_type_id=source_type_id,
        link=parsed.get("link", "").strip() or None,
        due_date=_parse_due_date(parsed.get("due_date", "")),
    )
    db.add(work_item)
    db.commit()
    return RedirectResponse(f"/programs/{program_id}/view", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/work-items/{work_item_id}/edit", response_class=HTMLResponse, include_in_schema=False)
def edit_work_item_page(work_item_id: int, db: Session = Depends(get_db)) -> str:
    work_item = db.scalars(
        select(WorkItem)
        .options(selectinload(WorkItem.source_type))
        .where(WorkItem.id == work_item_id)
    ).one_or_none()
    if work_item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work item not found")
    source_types = list(db.scalars(select(SourceType).order_by(SourceType.name.asc())))
    status_options = "".join(
        _select_option(work_status, work_status.replace("_", " ").title(), work_item.status)
        for work_status in WORK_ITEM_STATUSES
    )
    body = f"""
    <header>
      <div>
        <h1>Edit Work Item</h1>
        <div class="muted">{escape(work_item.title)}</div>
      </div>
      <a href="/programs/{work_item.program_id}/view">Back to Program</a>
    </header>
    <section class="panel">
      <form method="post" action="/work-items/{work_item.id}/update">
        <label for="title">Title</label>
        <input id="title" name="title" required maxlength="200" value="{escape(work_item.title)}">
        <label for="description">Description</label>
        <textarea id="description" name="description">{escape(work_item.description or "")}</textarea>
        <div class="compact-fields">
          <div>
            <label for="status">Status</label>
            <select id="status" name="status">{status_options}</select>
          </div>
          <div>
            <label for="owner">Owner</label>
            <input id="owner" name="owner" maxlength="120" value="{escape(work_item.owner or "")}">
          </div>
          <div>
            <label for="source_type_id">Source Type</label>
            <select id="source_type_id" name="source_type_id">{_source_type_options(source_types, work_item.source_type_id)}</select>
          </div>
          <div>
            <label for="due_date">Due Date</label>
            <input id="due_date" name="due_date" type="date" value="{escape(_format_date(work_item.due_date))}">
          </div>
          <div>
            <label for="link">Link</label>
            <input id="link" name="link" maxlength="500" value="{escape(work_item.link or "")}">
          </div>
        </div>
        <div class="actions">
          <button type="submit">Save Work Item</button>
          <a class="button secondary" href="/programs/{work_item.program_id}/view">Cancel</a>
        </div>
      </form>
    </section>
    """
    return _page_shell("Edit Work Item", body)


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
    source_type_id = _parse_optional_int(parsed.get("source_type_id", ""))
    if source_type_id is not None and db.get(SourceType, source_type_id) is None:
        source_type_id = None
    if title and work_status in WORK_ITEM_STATUSES:
        work_item.title = title
        work_item.description = parsed.get("description", "").strip() or None
        work_item.status = work_status
        work_item.owner = parsed.get("owner", "").strip() or None
        work_item.source_type_id = source_type_id
        work_item.link = parsed.get("link", "").strip() or None
        work_item.due_date = _parse_due_date(parsed.get("due_date", ""))
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


@router.get("/settings/source-types", response_class=HTMLResponse, include_in_schema=False)
def source_type_settings(db: Session = Depends(get_db)) -> str:
    source_types = list(db.scalars(select(SourceType).order_by(SourceType.name.asc())))
    rows = []
    for source_type in source_types:
        action = "Deactivate" if source_type.is_active else "Reactivate"
        action_path = "deactivate" if source_type.is_active else "activate"
        status_label = "Active" if source_type.is_active else "Inactive"
        rows.append(
            f"""
            <tr>
              <td>{escape(source_type.name)}</td>
              <td><span class="pill">{status_label}</span></td>
              <td>{escape(_format_datetime(source_type.updated_at))}</td>
              <td>
                <form method="post" action="/settings/source-types/{source_type.id}/{action_path}">
                  <button class="secondary" type="submit">{action}</button>
                </form>
              </td>
            </tr>
            """
        )
    body = f"""
    <header>
      <div>
        <h1>Settings</h1>
        <div class="muted">Work Item source types</div>
      </div>
      <a href="/">Back to Programs</a>
    </header>
    <div class="layout">
      <section class="panel">
        <h2>New Source Type</h2>
        <form method="post" action="/settings/source-types/create">
          <label for="name">Name</label>
          <input id="name" name="name" required maxlength="120">
          <div class="actions">
            <button type="submit">Create Source Type</button>
          </div>
        </form>
      </section>
      <section class="panel">
        <h2>Source Types</h2>
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Status</th>
              <th>Updated</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>{''.join(rows) or '<tr><td colspan="4" class="muted">No source types yet.</td></tr>'}</tbody>
        </table>
      </section>
    </div>
    """
    return _page_shell("Settings", body)


@router.post("/settings/source-types/create", include_in_schema=False)
async def create_source_type_from_ui(request: Request, db: Session = Depends(get_db)) -> RedirectResponse:
    parsed = await _parse_form(request)
    name = parsed.get("name", "").strip()
    if name:
        db.add(SourceType(name=name))
        db.commit()
    return RedirectResponse("/settings/source-types", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/settings/source-types/{source_type_id}/deactivate", include_in_schema=False)
def deactivate_source_type_from_ui(source_type_id: int, db: Session = Depends(get_db)) -> RedirectResponse:
    source_type = db.get(SourceType, source_type_id)
    if source_type is not None:
        source_type.is_active = False
        db.add(source_type)
        db.commit()
    return RedirectResponse("/settings/source-types", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/settings/source-types/{source_type_id}/activate", include_in_schema=False)
def activate_source_type_from_ui(source_type_id: int, db: Session = Depends(get_db)) -> RedirectResponse:
    source_type = db.get(SourceType, source_type_id)
    if source_type is not None:
        source_type.is_active = True
        db.add(source_type)
        db.commit()
    return RedirectResponse("/settings/source-types", status_code=status.HTTP_303_SEE_OTHER)
