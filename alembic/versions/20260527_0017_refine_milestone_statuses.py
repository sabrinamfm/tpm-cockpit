"""refine milestone statuses and remove owner

Revision ID: 20260527_0017
Revises: 20260527_0016
Create Date: 2026-05-27

Replaces milestone status vocabulary: removes 'in_progress' and 'missed',
adds 'on_track', 'at_risk', 'off_track', 'blocked'. Removes the owner
column. Backfill is embedded in the INSERT CASE expression so the old
table (still constrained to old values) is only ever read, never written:
  in_progress → on_track
  missed      → off_track
Table recreation is required because SQLite cannot ALTER CHECK constraints.
"""

import sqlalchemy as sa
from alembic import op

revision: str = "20260527_0017"
down_revision: str = "20260527_0016"
branch_labels = None
depends_on = None

_NEW_STATUSES = "'planned', 'on_track', 'at_risk', 'off_track', 'blocked', 'achieved', 'cancelled'"
_OLD_STATUSES = "'planned', 'in_progress', 'achieved', 'missed', 'cancelled'"


def upgrade() -> None:
    # Recreate milestones without owner column and with expanded status constraint.
    # Backfill is embedded in the CASE expression: the old table is only ever read,
    # never written, so the old CHECK constraint is never violated.
    op.execute(sa.text(f"""
        CREATE TABLE _milestones_new (
            id INTEGER NOT NULL PRIMARY KEY,
            display_id VARCHAR(20) NOT NULL,
            program_id INTEGER NOT NULL REFERENCES programs (id) ON DELETE CASCADE,
            title VARCHAR(200) NOT NULL,
            description TEXT,
            target_date DATE,
            status VARCHAR(50) NOT NULL DEFAULT 'planned',
            created_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP),
            updated_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP),
            CONSTRAINT ck_milestones_status_allowed CHECK (status in ({_NEW_STATUSES}))
        )
    """))
    op.execute(sa.text("""
        INSERT INTO _milestones_new
            (id, display_id, program_id, title, description, target_date, status, created_at, updated_at)
        SELECT id, display_id, program_id, title, description, target_date,
            CASE status
                WHEN 'in_progress' THEN 'on_track'
                WHEN 'missed'      THEN 'off_track'
                ELSE status
            END,
            created_at, updated_at
        FROM milestones
    """))
    op.execute(sa.text("DROP TABLE milestones"))
    op.execute(sa.text("ALTER TABLE _milestones_new RENAME TO milestones"))
    op.execute(sa.text("CREATE UNIQUE INDEX ix_milestones_display_id ON milestones (display_id)"))
    op.execute(sa.text("CREATE INDEX ix_milestones_program_id ON milestones (program_id)"))


def downgrade() -> None:
    # Recreate milestones with old status vocabulary and owner column.
    # Reverse mapping embedded in CASE: at_risk/blocked have no old equivalent → 'planned'.
    op.execute(sa.text(f"""
        CREATE TABLE _milestones_old (
            id INTEGER NOT NULL PRIMARY KEY,
            display_id VARCHAR(20) NOT NULL,
            program_id INTEGER NOT NULL REFERENCES programs (id) ON DELETE CASCADE,
            title VARCHAR(200) NOT NULL,
            description TEXT,
            target_date DATE,
            status VARCHAR(50) NOT NULL DEFAULT 'planned',
            owner VARCHAR(120),
            created_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP),
            updated_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP),
            CONSTRAINT ck_milestones_status_allowed CHECK (status in ({_OLD_STATUSES}))
        )
    """))
    op.execute(sa.text("""
        INSERT INTO _milestones_old
            (id, display_id, program_id, title, description, target_date, status, owner, created_at, updated_at)
        SELECT id, display_id, program_id, title, description, target_date,
            CASE status
                WHEN 'on_track'  THEN 'in_progress'
                WHEN 'off_track' THEN 'missed'
                WHEN 'at_risk'   THEN 'planned'
                WHEN 'blocked'   THEN 'planned'
                ELSE status
            END,
            NULL, created_at, updated_at
        FROM milestones
    """))
    op.execute(sa.text("DROP TABLE milestones"))
    op.execute(sa.text("ALTER TABLE _milestones_old RENAME TO milestones"))
    op.execute(sa.text("CREATE UNIQUE INDEX ix_milestones_display_id ON milestones (display_id)"))
    op.execute(sa.text("CREATE INDEX ix_milestones_program_id ON milestones (program_id)"))
