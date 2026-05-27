"""add decisions table

Revision ID: 20260527_0018
Revises: 20260527_0017
Create Date: 2026-05-27

Introduces Decisions as first-class objects (id, display_id, program_id,
title, description, decision_date, status, owner, rationale). Extends the
relationships table CHECK constraints to allow 'decision' as a valid object
type (requires table recreation in SQLite).
"""

import sqlalchemy as sa
from alembic import op

revision: str = "20260527_0018"
down_revision: str = "20260527_0017"
branch_labels = None
depends_on = None

_OLD_OBJECT_TYPES = "'work_item', 'dependency', 'risk', 'status_report', 'milestone'"
_NEW_OBJECT_TYPES = "'work_item', 'dependency', 'risk', 'status_report', 'milestone', 'decision'"
_REL_TYPES = (
    "'relates_to', 'blocks', 'blocked_by', 'mitigates',"
    " 'tracks', 'highlights', 'duplicates', 'depends_on'"
)


def upgrade() -> None:
    # 1. Create decisions table
    op.create_table(
        "decisions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("display_id", sa.String(20), nullable=False),
        sa.Column("program_id", sa.Integer, sa.ForeignKey("programs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("decision_date", sa.Date, nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="proposed"),
        sa.Column("owner", sa.String(120), nullable=True),
        sa.Column("rationale", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
        ),
        sa.CheckConstraint(
            "status in ('proposed', 'decided', 'deferred', 'superseded', 'cancelled')",
            name="ck_decisions_status_allowed",
        ),
    )
    op.create_index("ix_decisions_display_id", "decisions", ["display_id"], unique=True)
    op.create_index("ix_decisions_program_id", "decisions", ["program_id"])

    # 2. Expand relationships object-type constraints to include 'decision'.
    #    SQLite cannot ALTER CHECK constraints; the table must be recreated.
    op.execute(sa.text(f"""
        CREATE TABLE _relationships_new (
            id INTEGER NOT NULL PRIMARY KEY,
            display_id VARCHAR(20) NOT NULL,
            source_type VARCHAR(20) NOT NULL,
            source_id INTEGER NOT NULL,
            relationship_type VARCHAR(20) NOT NULL,
            target_type VARCHAR(20) NOT NULL,
            target_id INTEGER NOT NULL,
            note TEXT,
            created_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP),
            updated_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP),
            CONSTRAINT ck_relationships_source_type CHECK (source_type in ({_NEW_OBJECT_TYPES})),
            CONSTRAINT ck_relationships_target_type CHECK (target_type in ({_NEW_OBJECT_TYPES})),
            CONSTRAINT ck_relationships_type CHECK (relationship_type in ({_REL_TYPES})),
            CONSTRAINT ck_relationships_no_self CHECK (NOT (source_type = target_type AND source_id = target_id))
        )
    """))
    op.execute(sa.text("INSERT INTO _relationships_new SELECT * FROM relationships"))
    op.execute(sa.text("DROP TABLE relationships"))
    op.execute(sa.text("ALTER TABLE _relationships_new RENAME TO relationships"))
    op.execute(sa.text("CREATE UNIQUE INDEX ix_relationships_display_id ON relationships (display_id)"))
    op.execute(sa.text("CREATE INDEX ix_relationships_source ON relationships (source_type, source_id)"))
    op.execute(sa.text("CREATE INDEX ix_relationships_target ON relationships (target_type, target_id)"))


def downgrade() -> None:
    # Remove decision-type relationships before tightening constraints.
    op.execute(sa.text("DELETE FROM relationships WHERE source_type = 'decision' OR target_type = 'decision'"))
    op.execute(sa.text(f"""
        CREATE TABLE _relationships_old (
            id INTEGER NOT NULL PRIMARY KEY,
            display_id VARCHAR(20) NOT NULL,
            source_type VARCHAR(20) NOT NULL,
            source_id INTEGER NOT NULL,
            relationship_type VARCHAR(20) NOT NULL,
            target_type VARCHAR(20) NOT NULL,
            target_id INTEGER NOT NULL,
            note TEXT,
            created_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP),
            updated_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP),
            CONSTRAINT ck_relationships_source_type CHECK (source_type in ({_OLD_OBJECT_TYPES})),
            CONSTRAINT ck_relationships_target_type CHECK (target_type in ({_OLD_OBJECT_TYPES})),
            CONSTRAINT ck_relationships_type CHECK (relationship_type in ({_REL_TYPES})),
            CONSTRAINT ck_relationships_no_self CHECK (NOT (source_type = target_type AND source_id = target_id))
        )
    """))
    op.execute(sa.text("INSERT INTO _relationships_old SELECT * FROM relationships"))
    op.execute(sa.text("DROP TABLE relationships"))
    op.execute(sa.text("ALTER TABLE _relationships_old RENAME TO relationships"))
    op.execute(sa.text("CREATE UNIQUE INDEX ix_relationships_display_id ON relationships (display_id)"))
    op.execute(sa.text("CREATE INDEX ix_relationships_source ON relationships (source_type, source_id)"))
    op.execute(sa.text("CREATE INDEX ix_relationships_target ON relationships (target_type, target_id)"))

    op.drop_index("ix_decisions_program_id", table_name="decisions")
    op.drop_index("ix_decisions_display_id", table_name="decisions")
    op.drop_table("decisions")
