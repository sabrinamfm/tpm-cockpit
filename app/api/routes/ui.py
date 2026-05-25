from html import escape
from typing import Optional
from urllib.parse import parse_qs, urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.domain.programs import program_attention_state
from app.models import Program

router = APIRouter(tags=["ui"])

PROGRAM_STATUSES = ("active", "paused", "completed", "archived")
ATTENTION_STATES = ("Needs attention", "Paused", "Archived", "OK")
SORTS = {
    "name": Program.name.asc(),
    "status": Program.status.asc(),
    "updated_at": Program.updated_at.desc(),
}


def _format_datetime(value) -> str:
    return value.strftime("%Y-%m-%d %H:%M") if value else ""


def _select_option(value: str, label: str, selected: Optional[str]) -> str:
    selected_attr = " selected" if value == selected else ""
    return f'<option value="{escape(value)}"{selected_attr}>{escape(label)}</option>'


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
    main {{ max-width: 1180px; margin: 0 auto; padding: 32px 20px 48px; }}
    header {{ display: flex; align-items: end; justify-content: space-between; gap: 20px; margin-bottom: 24px; }}
    h1 {{ margin: 0; font-size: 30px; font-weight: 720; }}
    h2 {{ margin: 0 0 14px; font-size: 18px; }}
    h3 {{ margin: 0 0 8px; font-size: 15px; }}
    a {{ color: #2364aa; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
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
    button.danger {{ background: #b42318; }}
    .actions {{ display: flex; gap: 8px; margin-top: 14px; flex-wrap: wrap; }}
    .filters {{ display: grid; grid-template-columns: repeat(4, minmax(120px, 1fr)); gap: 12px; align-items: end; margin-bottom: 16px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ padding: 10px; border-bottom: 1px solid #e2e7ef; text-align: left; vertical-align: top; font-size: 14px; }}
    th {{ color: #526071; font-size: 12px; text-transform: uppercase; }}
    .row-actions {{ display: flex; gap: 6px; justify-content: flex-end; }}
    .pill {{ display: inline-block; border-radius: 999px; padding: 3px 8px; font-size: 12px; font-weight: 700; background: #eef2f7; color: #344054; }}
    .attention {{ background: #fff3cd; color: #7a4d00; }}
    .ok {{ background: #e7f5ec; color: #246b3d; }}
    .detail-grid {{ display: grid; grid-template-columns: repeat(2, minmax(180px, 1fr)); gap: 12px; margin: 16px 0; }}
    .placeholder-grid {{ display: grid; grid-template-columns: repeat(2, minmax(220px, 1fr)); gap: 14px; }}
    .placeholder {{ min-height: 86px; }}
    @media (max-width: 860px) {{
      header, .layout {{ display: block; }}
      .panel {{ margin-bottom: 18px; }}
      .filters, .detail-grid, .placeholder-grid {{ grid-template-columns: 1fr; }}
      th:nth-child(2), td:nth-child(2) {{ display: none; }}
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
    if sort not in SORTS:
        sort = "updated_at"

    statement = select(Program)
    if status_filter:
        statement = statement.where(Program.status == status_filter)
    statement = statement.order_by(SORTS[sort], Program.id.desc())
    programs = list(db.scalars(statement))
    if attention_filter:
        programs = [
            program
            for program in programs
            if program_attention_state(program) == attention_filter
        ]

    status_options = '<option value="">All statuses</option>' + "".join(
        _select_option(status, status.title(), status_filter) for status in PROGRAM_STATUSES
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
                <form method="post" action="/programs/{program.id}/delete">
                  <button class="danger" type="submit">Delete</button>
                </form>
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
      <a href="/docs">API docs</a>
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
              <th></th>
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
    form_data = await request.body()
    parsed = parse_qs(form_data.decode())

    name = parsed.get("name", [""])[0].strip()
    description = parsed.get("description", [""])[0].strip() or None
    program_status = parsed.get("status", ["active"])[0]
    if not name or program_status not in PROGRAM_STATUSES:
        return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)

    program = Program(name=name, description=description, status=program_status)
    db.add(program)
    db.commit()
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/programs/{program_id}/delete", include_in_schema=False)
def delete_program_from_ui(program_id: int, db: Session = Depends(get_db)) -> RedirectResponse:
    program = db.get(Program, program_id)
    if program is not None:
        db.delete(program)
        db.commit()
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/programs/{program_id}/view", response_class=HTMLResponse, include_in_schema=False)
def program_detail(program_id: int, db: Session = Depends(get_db)) -> str:
    program = db.get(Program, program_id)
    if program is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")

    attention = program_attention_state(program)
    attention_class = "ok" if attention == "OK" else "attention"
    placeholder_sections = "".join(
        f"""
        <section class="panel placeholder">
          <h3>{title}</h3>
          <div class="muted">Not implemented yet.</div>
        </section>
        """
        for title in ("Work Items", "Risks", "Dependencies", "Decisions", "Notes")
    )
    body = f"""
    <header>
      <div>
        <h1>{escape(program.name)}</h1>
        <div class="muted">Program detail</div>
      </div>
      <a href="/">Back to Programs</a>
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
    <div class="placeholder-grid">
      {placeholder_sections}
    </div>
    """
    return _page_shell(program.name, body)
