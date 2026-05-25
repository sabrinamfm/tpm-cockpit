"""enforce program status values

Revision ID: 20260525_0002
Revises: 20260525_0001
Create Date: 2026-05-25 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260525_0002"
down_revision: Union[str, None] = "20260525_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("update programs set status = 'completed' where status = 'complete'")
    with op.batch_alter_table("programs") as batch_op:
        batch_op.create_check_constraint(
            "ck_programs_status_allowed",
            "status in ('active', 'paused', 'completed', 'archived')",
        )


def downgrade() -> None:
    with op.batch_alter_table("programs") as batch_op:
        batch_op.drop_constraint("ck_programs_status_allowed", type_="check")
