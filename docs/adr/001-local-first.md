# ADR-001 — Local-First Architecture

## Status
Accepted

## Context

TPM Cockpit is intended for operational TPM work, including potentially sensitive coordination and program information.

The product should remain usable without cloud infrastructure.

## Decision

TPM Cockpit will use a local-first architecture:
- SQLite local database
- local workspace ownership
- Gitignored operational data
- no cloud dependency in Phase 1

## Consequences

Benefits:
- safer experimentation
- easier onboarding
- lower operational complexity
- offline capability

Tradeoffs:
- no multi-user collaboration initially
- limited scalability
- future sync complexity