# Changelog

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