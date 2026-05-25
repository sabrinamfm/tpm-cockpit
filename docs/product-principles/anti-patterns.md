# Anti-Patterns

## Purpose

This file captures what TPM Cockpit should avoid becoming.

## Product Anti-Patterns

TPM Cockpit should not become:

- generic Jira
- generic Trello
- generic Notion
- sprint planning software
- engineering backlog software
- executive dashboard theater
- status-report generator with no operational grounding

## Implementation Anti-Patterns

Avoid:

- deleting local user data during updates
- committing real work data
- overbuilding before Phase 1 is usable
- creating complex abstractions too early
- adding integrations before the local workflow works

## Guiding Rule

If a feature does not improve TPM operational awareness, coordination, or reporting readiness, question whether it belongs in the product.