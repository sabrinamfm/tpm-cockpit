# ADR-003 — Jinja Template Refactor

## Status
Accepted

## Context

The initial implementation rendered HTML directly from Python f-strings inside ui.py.

As the application grew, this created maintainability and readability issues.

## Decision

The UI rendering layer was migrated to Jinja templates.

Templates are now separated into:
- base layout
- page templates
- reusable partials

## Consequences

Benefits:
- improved maintainability
- clearer separation of concerns
- easier future UI evolution
- reduced rendering complexity

Tradeoffs:
- additional template structure
- slightly more indirection during debugging