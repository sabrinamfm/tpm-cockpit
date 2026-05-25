"""create dependencies

Revision ID: 20260525_0006
Revises: 20260525_0005
Create Date: 2026-05-25 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260525_0006"
down_revision: Union[str, None] = "20260525_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "dependencies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("program_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("dependency_type", sa.String(length=50), nullable=False),
        sa.Column("owner", sa.String(length=120), nullable=True),
        sa.Column("external_team", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=50), server_default="open", nullable=False),
        sa.Column("blocking_level", sa.String(length=50), server_default="medium", nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("last_confirmation_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "dependency_type in ('team', 'approval', 'infrastructure', 'release', 'vendor', 'legal', 'finance', 'security', 'product', 'technical', 'operational')",
            name="ck_dependencies_type_allowed",
        ),
        sa.CheckConstraint(
            "status in ('open', 'in_progress', 'confirmed', 'blocked', 'resolved', 'cancelled')",
            name="ck_dependencies_status_allowed",
        ),
        sa.CheckConstraint(
            "blocking_level in ('low', 'medium', 'high', 'critical')",
            name="ck_dependencies_blocking_level_allowed",
        ),
        sa.ForeignKeyConstraint(["program_id"], ["programs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_dependencies_id"), "dependencies", ["id"], unique=False)
    op.create_index(op.f("ix_dependencies_program_id"), "dependencies", ["program_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_dependencies_program_id"), table_name="dependencies")
    op.drop_index(op.f("ix_dependencies_id"), table_name="dependencies")
    op.drop_table("dependencies")
