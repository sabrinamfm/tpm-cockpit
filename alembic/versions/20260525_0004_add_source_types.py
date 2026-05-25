"""add source types

Revision ID: 20260525_0004
Revises: 20260525_0003
Create Date: 2026-05-25 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260525_0004"
down_revision: Union[str, None] = "20260525_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "source_types",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_source_types_id"), "source_types", ["id"], unique=False)

    with op.batch_alter_table("work_items") as batch_op:
        batch_op.add_column(sa.Column("source_type_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("link", sa.String(length=500), nullable=True))
        batch_op.create_foreign_key(
            "fk_work_items_source_type_id_source_types",
            "source_types",
            ["source_type_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(op.f("ix_work_items_source_type_id"), ["source_type_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("work_items") as batch_op:
        batch_op.drop_index(op.f("ix_work_items_source_type_id"))
        batch_op.drop_constraint("fk_work_items_source_type_id_source_types", type_="foreignkey")
        batch_op.drop_column("link")
        batch_op.drop_column("source_type_id")

    op.drop_index(op.f("ix_source_types_id"), table_name="source_types")
    op.drop_table("source_types")
