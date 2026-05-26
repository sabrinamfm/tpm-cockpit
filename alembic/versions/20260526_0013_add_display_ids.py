"""add display_ids to core objects

Revision ID: 20260526_0013
Revises: 20260526_0012
Create Date: 2026-05-26
"""

import sqlalchemy as sa
from alembic import op

revision: str = "20260526_0013"
down_revision: str = "20260526_0012"
branch_labels = None
depends_on = None

_TABLES = [
    ("programs", "PRG"),
    ("work_items", "WI"),
    ("dependencies", "DEP"),
    ("risks", "RSK"),
    ("status_reports", "SR"),
]


def upgrade() -> None:
    for table, prefix in _TABLES:
        op.add_column(table, sa.Column("display_id", sa.String(20), nullable=True))
        op.execute(
            f"UPDATE {table} SET display_id = '{prefix}-' || printf('%03d', id)"
            f" WHERE display_id IS NULL"
        )
        op.create_index(f"ix_{table}_display_id", table, ["display_id"], unique=True)


def downgrade() -> None:
    for table, _ in reversed(_TABLES):
        op.drop_index(f"ix_{table}_display_id", table_name=table)
        op.drop_column(table, "display_id")
