# TPM Cockpit — Codex Instructions

## Project goal
Build a local-first TPM Cockpit: a lightweight task/program workspace for Technical Program Managers.

## Technical stack
Use Python.

Initial stack:
- FastAPI for the backend API
- SQLite for local persistence
- SQLAlchemy for database models
- Alembic for migrations
- Pytest for tests

## Data safety rule
Never commit real user/work data.

The `data/` folder is ignored by Git and may contain:
- cockpit.db
- attachments/
- exports/
- backups/

Use `sample_data/` for fake demo data only.

## Phase 1 scope
Implement:
- Programs
- Work items
- Risks
- Dependencies
- Decisions
- Stakeholders
- Notes

## Product principle
This is not generic Jira. It is a TPM-native cockpit focused on coordination, attention, ambiguity, blockers, risks, dependencies, and reporting readiness.

## Development rules
- Make small commits.
- Add tests for every core behavior.
- Do not reset or delete the SQLite database.
- Use Alembic migrations for schema changes.
- Keep secrets in `.env`; never commit them.