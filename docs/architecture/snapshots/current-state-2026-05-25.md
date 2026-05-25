---
  Architecture Verification Report

  Summary

  The docs in this repo fall into two categories: accurate strategic guidance (CLAUDE.md rules, product principles) and outdated/incomplete state descriptions (README, domain model docs). The actual implementation is significantly further along than most docs suggest.

  ---
  README.md — Significantly Outdated

  Says: "contains only the Python/FastAPI foundation: health-check endpoint, Pytest test coverage for the health check"

  Actual state:
  - 5 fully-implemented domain models: Program, WorkItem, Dependency, ProgramStatus, SourceType
  - 6 Jinja2 templates + a full UI router (ui.py)
  - 9 migrations
  - ~980 lines of tests across 9 test files covering all major entities, attention logic, and UI routes

  Verdict: outdated, not verified against code.

  ---
  CLAUDE.md (app/CLAUDE.md) — Partially Outdated

  The product model listed is:
  Program → Work Items → Risks → Dependencies → Decisions → Notes

  What's implemented: Program, WorkItems, Dependencies — plus two settings entities (ProgramStatus, SourceType) not listed here.

  Not implemented at all: Risks, Decisions, Notes, Stakeholders, Updates (no models, migrations, or routes exist for any of these).

  Verdict: The listed objects are aspirational, not current. The missing two implemented entities (ProgramStatus, SourceType) are absent from the
  model. This is an assumption-as-fact problem — the doc reads as if these objects are already built.

  ---
  docs/domain-model/core-objects.md — Aspirational, Not Implemented

  Lists 8 objects: Program, Work Item, Risk, Dependency, Decision, Stakeholder, Update, Note.

  Implemented: 3 of 8 (Program, WorkItem, Dependency).

  Not implemented: Risk, Decision, Stakeholder, Update, Note — zero code for any of these.

  No marker distinguishes "planned" from "built." A reader cannot tell what exists.

  ---
  docs/domain-model/attention-model.md — Partially Implemented

  Phase 1 signals listed:
  - Work item overdue ✓ — implemented in program_attention_state
  - Work item blocked ✓ — implemented in program_attention_state
  - Dependency not updated recently — partially: dependency_is_stale exists in domain/dependencies.py and is a Jinja2 global, but it does not feed into program_attention_state
  - Risk open and high severity — not implemented (no Risk model)
  - Decision pending — not implemented
  - Item has no owner — not implemented (not checked anywhere)

  Additional signals from the doc (stale, missing next step, linked to risk/decision):
  - work_item_is_stale exists and is a Jinja2 global for display, but is not used in program_attention_state — stale work items do not put a program into "Needs attention"
  
  Verdict: program_attention_state implements only 2 of the listed signals (blocked + overdue). Staleness, ownership, and dependency staleness are computed but not wired into program-level attention.

  ---
  Migrations — Chain is Complete and Correct

  Sequence 0001 → 0009 is a clean linear chain with no branches or gaps.

  Notable migration behavior:
  - 0002 adds CHECK(status in ('active','paused','completed','archived')) on programs
  - 0008 drops that column and constraint, adds status_id FK to program_statuses
  - 0009 backfills slug from name for existing source_types rows

  One discrepancy: The Program model defines the FK as ForeignKey("program_statuses.id", ondelete="RESTRICT"), but migration 0008'sncreate_foreign_key call does not specify ondelete. SQLite doesn't enforce FK constraints by default anyway, but the model and migration are inconsistent here. The RESTRICT behavior is enforced at the application level in the delete handler (reassigns programs before deleting a status), not at the DB level.

  Migration 0004 (source_types): creates the table without slug or sort_order — these are added in 0009. The current SourceType model has both columns NOT NULL, which is only safe because 0009 backfills values before making them NOT NULL. Correct, but the gap between 0004 and the current model is a potential source of confusion.

  ---
  Model Relationships — Accurate to Code, Undocumented

  The actual relationships:
  - Program → ProgramStatus (many-to-one, lazy=joined, RESTRICT on delete)
  - Program → WorkItem (one-to-many, cascade all+delete-orphan) 
  - Program → Dependency (one-to-many, cascade all+delete-orphan)
  - WorkItem → SourceType (many-to-one, SET NULL on delete)

  No doc describes these relationships. docs/domain-model/relationships.md exists but is empty (contains only the heading # Relationships).

  ---
  Constraints — Correct in Code, Undocumented

  ┌──────────────────┬──────────────────────────┬──────────────────────────────────────────────────┐
  │      Table       │      Constraint          │                      Values                      │
  ├──────────────────┼──────────────────────────┼──────────────────────────────────────────────────┤
  │ work_items       │ CHECK status             │ open, in_progress, blocked, completed, cancelled │
  ├──────────────────┼──────────────────────────┼──────────────────────────────────────────────────┤
  │ work_items       │ CHECK priority           │ low, medium, high, critical                      │
  ├──────────────────┼──────────────────────────┼──────────────────────────────────────────────────┤
  │ dependencies     │ CHECK dependency_type    │ 11 values (team, approval, infrastructure, ...)  │
  ├──────────────────┼──────────────────────────┼──────────────────────────────────────────────────┤
  │ dependencies     │ CHECK status             │ 6 values (open, in_progress, confirmed, ...)     │
  ├──────────────────┼──────────────────────────┼──────────────────────────────────────────────────┤
  │ dependencies     │ CHECK blocking_level     │ low, medium, high, critical                      │
  ├──────────────────┼──────────────────────────┼──────────────────────────────────────────────────┤
  │ program_statuses │ UNIQUE slug              │ —                                                │
  ├──────────────────┼──────────────────────────┼──────────────────────────────────────────────────┤
  │ source_types     │ UNIQUE name, UNIQUE slug │ —                                                │
  └──────────────────┴──────────────────────────┴──────────────────────────────────────────────────┘

  All CHECK constraints are present in both models and migrations. No doc mentions any of these.

  ---
  Settings Behavior — Correct but Undocumented

  - Single /settings page with two sections (#program-statuses, #source-types), navigated via anchors
  - Old URLs /settings/source-types and /settings/program-statuses redirect to the unified page via 301
  - seed_default_program_statuses is called at request time (on GET / and GET /settings) — idempotent, runs only when the program_statuses table is empty
  - Status deletion transfers is_default to the replacement and reassigns all programs — prevents orphaned programs
  - At most one is_default is enforced via a bulk UPDATE in the update handler, not a DB constraint

  No doc describes any of this behavior.

  ---
  UI/Template Structure — Correct, Not Documented
  
  Templates: base.html, index.html, program_detail.html, edit_program.html, confirm_delete.html (reusable), settings.html.

  The claim "forms hidden until needed" in CLAUDE.md is accurate: create forms use <details> elements; edit forms render inline on the row when edit_*_id matches.

  The README statement that templates use Jinja2 is accurate. The refactor from f-string HTML to Jinja2 (from recent commits) is reflected in the current code — no f-string HTML routes remain.

  ---
  Test Coverage — Broader Than Claimed

  README says only health-check tests exist. Actual coverage:
  - All CRUD paths for Programs, WorkItems, Dependencies, ProgramStatuses, SourceTypes via API
  - UI routes (index, detail, create/edit/delete work items and dependencies, settings)
  - Attention state logic (blocked, overdue edge cases)
  - Dependency staleness logic
  
  Not covered by tests:
  - Reorder endpoints (/settings/*/reorder)
  - The 301 redirect routes for old settings URLs
  - program_attention_state does not test stale work items (not wired into it anyway)
  - No test validates that deleting the last status is blocked

  ---
  Top Issues to Address
  
  1. README needs to be updated — it actively misrepresents the project state.
  2. CLAUDE.md product model conflates implemented with planned; Risks/Decisions/Notes/Stakeholders are not built.
  3. docs/domain-model/relationships.md is empty — the actual FK structure is undocumented.
  4. Attention model doc lists signals that are not yet wired into program_attention_state (staleness, dependency staleness, ownership).
  5. ondelete="RESTRICT" in Program model is not reflected in migration 0008's create_foreign_key call — behavioral gap between model declaration and actual DB schema.
  6. seed_default_program_statuses called at request time is an architectural pattern not mentioned anywhere — it could surprise a reader expecting migration-only seeding.

  ---
 Current Product Maturity
 
 The product is currently transitioning from:
 - object management
 to:
 - operational coordination visibility
 
 Implemented operational semantics:
 - blocked work detection
 - overdue work detection
 - stale work detection
 - stale dependency detection
 - critical dependency visibility
 - Morning View operational overview
 
 The product is not yet:
 - an analytics platform
 - an executive reporting system
 - a multi-user collaboration system
 - AI-driven