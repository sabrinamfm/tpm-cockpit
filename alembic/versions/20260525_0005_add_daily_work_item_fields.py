"""add daily work item fields

Revision ID: 20260525_0005
Revises: 20260525_0004
Create Date: 2026-05-25 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260525_0005"
down_revision: Union[str, None] = "20260525_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("work_items") as batch_op:
        batch_op.add_column(sa.Column("priority", sa.String(length=50), server_default="medium", nullable=False))
        batch_op.add_column(sa.Column("next_step", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("last_touched_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_check_constraint(
            "ck_work_items_priority_allowed",
            "priority in ('low', 'medium', 'high', 'critical')",
        )


def downgrade() -> None:
    with op.batch_alter_table("work_items") as batch_op:
        batch_op.drop_constraint("ck_work_items_priority_allowed", type_="check")
        batch_op.drop_column("last_touched_at")
        batch_op.drop_column("next_step")
        batch_op.drop_column("priority")
