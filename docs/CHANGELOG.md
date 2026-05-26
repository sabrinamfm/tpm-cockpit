# Changelog

## 2026-05-26

### Risks
- Added Risk model, CRUD API, predicates (is_stale, is_critical), and UI
- Added risk sections to program detail and morning view
- Risks cascade-delete with their program

### Program Health
- Added five-state computed health signal (inactive, on_track, needs_attention, at_risk, off_track)
- Health shown on program list with filtering and on program detail with evidence summary
- Morning view organises programs into health-state buckets

### Status Reports
- Added StatusReport model, CRUD API, and UI
- TPM declares reported_health; server computes suggested_health from live signals at creation
- Divergence indicator shown when reported and suggested health differ
- Latest report shown on program list; full history on program detail

### Display IDs
- Added stable display IDs to all five core objects: PRG-NNN, WI-NNN, DEP-NNN, RSK-NNN, SR-NNN
- IDs assigned at insert via before_insert mapper event; stored in the database; never recomputed
- All *Read schemas expose display_id as a required str field
- IDs rendered in program list, program detail, and morning view

## 2026-05-25

### Foundation
- Initialized TPM Cockpit local-first architecture
- Added FastAPI + SQLite + SQLAlchemy + Alembic stack
- Added pytest test structure
- Added Swagger/OpenAPI support

### Programs
- Added Program model and CRUD operations
- Added Program detail page
- Added filtering and sorting

### Work Items
- Added Work Item model and CRUD operations
- Added filtering and sorting
- Added source types
- Added priority, next step, due dates, stale indicators
- Added collapsible creation/editing forms

### Dependencies
- Added Dependency model and CRUD operations
- Added stale confirmation tracking
- Added filtering and sorting

### Configuration
- Added configurable Program Statuses
- Added Settings page
- Added drag-to-reorder behavior

### UI
- Refactored from inline f-string HTML to Jinja templates
- Added shared template structure
- Improved collapsible operational workflow patterns

### Architecture
- Added CLAUDE.md and CODEX.md
- Established local-first and repository safety rules