# TPM Cockpit

## Purpose
Local-first TPM operational workspace.

Not generic project management software.

## Product Direction
Optimize for:
- coordination
- operational visibility
- dependencies
- execution tracking
- attention routing

Avoid:
- sprint tooling
- generic agile workflows
- enterprise dashboard clutter

## Technical Stack
- Python
- FastAPI
- SQLite
- SQLAlchemy
- Alembic
- server-rendered HTML

## Architecture Rules
- local-first
- never overwrite local data
- use migrations
- keep implementation simple
- prefer explicit models over abstractions

## UI Rules
- operational UI
- dense but readable
- forms hidden until needed
- lists visible by default
- avoid unnecessary navigation

## Development Rules
- small commits
- preserve backward compatibility
- avoid premature optimization
- avoid frontend framework complexity
- no React unless explicitly needed

## Current Product Model
Program
→ Work Items
→ Dependencies
→ Risks
→ Status Reports
→ Relationships (cross-object, typed, directional)

## Planned Product Model
Program
→ Work Items
→ Dependencies
→ Risks
→ Status Reports
→ Relationships
→ Decisions
→ Notes

## Important Terminology
Use "Work Item" instead of "Task".