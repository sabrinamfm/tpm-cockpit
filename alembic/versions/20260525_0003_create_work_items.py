"""create work items

Revision ID: 20260525_0003
Revises: 20260525_0002
Create Date: 2026-05-25 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260525_0003"
down_revision: Union[str, None] = "20260525_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "work_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("program_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), server_default="open", nullable=False),
        sa.Column("owner", sa.String(length=120), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status in ('open', 'in_progress', 'blocked', 'completed', 'cancelled')",
            name="ck_work_items_status_allowed",
        ),
        sa.ForeignKeyConstraint(["program_id"], ["programs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_work_items_id"), "work_items", ["id"], unique=False)
    op.create_index(op.f("ix_work_items_program_id"), "work_items", ["program_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_work_items_program_id"), table_name="work_items")
    op.drop_index(op.f("ix_work_items_id"), table_name="work_items")
    op.drop_table("work_items")
