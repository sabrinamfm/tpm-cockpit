"""make display_ids NOT NULL on all core objects

Revision ID: 20260526_0014
Revises: 20260526_0013
Create Date: 2026-05-26

Migration 0013 backfilled every existing row. The before_insert event in
session.py now sets display_id before the INSERT is emitted, so new rows
never arrive with a NULL value. It is safe to enforce NOT NULL.
"""

import sqlalchemy as sa
from alembic import op

revision: str = "20260526_0014"
down_revision: str = "20260526_0013"
branch_labels = None
depends_on = None

_TABLES = [
    "programs",
    "work_items",
    "dependencies",
    "risks",
    "status_reports",
]


def upgrade() -> None:
    for table in _TABLES:
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column(
                "display_id",
                existing_type=sa.String(20),
                nullable=False,
            )


def downgrade() -> None:
    for table in reversed(_TABLES):
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column(
                "display_id",
                existing_type=sa.String(20),
                nullable=True,
            )
