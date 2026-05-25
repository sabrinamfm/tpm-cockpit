"""Add is_operational to program_statuses

Revision ID: 20260525_0010
Revises: 20260525_0009
Create Date: 2026-05-25
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260525_0010"
down_revision: Union[str, None] = "20260525_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("program_statuses") as batch_op:
        batch_op.add_column(sa.Column("is_operational", sa.Boolean(), nullable=True))

    conn = op.get_bind()
    # Active is the only operational status by default
    conn.execute(sa.text("UPDATE program_statuses SET is_operational = 1 WHERE slug = 'active'"))
    # All other statuses (including any user-created ones) default to non-operational
    conn.execute(sa.text("UPDATE program_statuses SET is_operational = 0 WHERE is_operational IS NULL"))

    with op.batch_alter_table("program_statuses") as batch_op:
        batch_op.alter_column("is_operational", nullable=False, server_default="0")


def downgrade() -> None:
    with op.batch_alter_table("program_statuses") as batch_op:
        batch_op.drop_column("is_operational")
