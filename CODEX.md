# TPM Cockpit — Codex Instructions

## Project Goal

Build a local-first TPM Cockpit: a lightweight operational workspace for Technical Program Managers.

The product should help TPMs manage programs, work items, risks, dependencies, decisions, stakeholders, notes, and reporting inputs.

## Technical Stack

Use Python.

Initial stack:

- FastAPI
- SQLite
- SQLAlchemy
- Alembic
- Pytest

## Data Safety

Never commit real user or work data.

The `data/` folder is ignored by Git and may contain:

- cockpit.db
- attachments/
- exports/
- backups/

Use `sample_data/` for fake demo data only.

## Development Rules

- Keep the app local-first.
- Do not reset or delete the SQLite database.
- Use Alembic migrations for schema changes.
- Keep secrets in `.env`; never commit them.
- Keep changes small and reviewable.
- Add tests for core behavior.
- Prefer simple, explicit code over clever abstractions.
- Do not introduce cloud dependencies in Phase 1.

## Product Principles

TPM Cockpit is not generic project management software.

Optimize for:

- TPM workflows
- operational visibility
- coordination tracking
- dependency awareness
- risk visibility
- decision memory
- reporting readiness

Avoid optimizing for:

- sprint management
- engineering backlog ownership
- executive vanity dashboards
- generic productivity workflows