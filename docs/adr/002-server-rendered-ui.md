# ADR-002 — Server-Rendered UI

## Status
Accepted

## Context

The product is currently a local operational tool focused on rapid iteration and workflow discovery.

Frontend framework complexity would slow development significantly.

## Decision

TPM Cockpit will use:
- FastAPI
- Jinja templates
- server-rendered HTML

React and SPA architecture are intentionally avoided in the current phase.

## Consequences

Benefits:
- simpler architecture
- faster iteration
- lower tooling complexity
- easier AI-assisted development

Tradeoffs:
- less interactive UI
- fewer client-side capabilities
- future frontend migration may require refactoring