# TPM Cockpit

Local-first operational workspace for Technical Program Managers.

## What's implemented

**Models (SQLAlchemy + SQLite via Alembic migrations):**

- `Program` — top-level initiative; linked to a `ProgramStatus` via FK
- `WorkItem` — actionable work within a program; supports status, priority, owner, source type, due date, next step, last-touched timestamp
- `Dependency` — cross-team or external dependency; supports type, blocking level, owner, external team, confirmation timestamp
- `ProgramStatus` — configurable statuses (name, slug, color, sort order, default flag); seeded with Active/Paused/Completed/Archived on first run
- `SourceType` — configurable work item source labels (e.g. Jira, Slack); supports slug and sort order

**UI (server-rendered via Jinja2 templates):**

- Program list with status and attention-state filtering, sort by name/status/updated
- Program detail with inline work item and dependency management (create, edit, delete, touch/confirm)
- Attention state: programs are flagged "Needs attention" when any work item is blocked or overdue
- Settings page (`/settings`) — manage program statuses and source types; drag-to-reorder; edit/delete in place
- Confirm-before-delete flow for programs, work items, and dependencies

**JSON API (FastAPI):**

Available alongside the UI at the same routes (prefix `/programs`, `/work-items`, `/dependencies`, `/program-statuses`, `/source-types`). Useful for scripting or future integrations.

**Not yet implemented:** Risks, Decisions, Notes, Stakeholders — these are in the domain model docs as planned objects.

## Local-first design

All data lives in `data/cockpit.db` (SQLite). The `data/` directory is git-ignored. No external services, no sync, no accounts. Migrations are additive — existing data is never overwritten.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Copy `.env.example` to `.env` to override the default database path:

```text
sqlite:///./data/cockpit.db
```

## Run

```bash
uvicorn app.main:app --reload
```

Open `http://localhost:8000` in a browser.

Health check: `curl http://localhost:8000/health`

## Migrations

Apply all migrations to bring the database to the current schema:

```bash
alembic upgrade head
```

Create a new migration after changing a model:

```bash
alembic revision --autogenerate -m "describe change"
```

Nine migrations exist in sequence (0001–0009). They are non-destructive: new tables and columns are added; no data is dropped without a backfill step.

## Tests

```bash
pytest
```

Tests use an in-memory SQLite database per test (via `tmp_path`). Coverage includes:

- Program, WorkItem, Dependency, ProgramStatus, SourceType CRUD via JSON API
- UI routes (program list, detail, settings, create/edit/delete flows)
- Attention state logic (blocked, overdue)
- Dependency staleness logic
