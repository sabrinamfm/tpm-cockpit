"""Add slug and sort_order to source_types

Revision ID: 20260525_0009
Revises: 20260525_0008
Create Date: 2026-05-25
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260525_0009"
down_revision: Union[str, None] = "20260525_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("source_types") as batch_op:
        batch_op.add_column(sa.Column("slug", sa.String(50), nullable=True))
        batch_op.add_column(
            sa.Column("sort_order", sa.Integer(), nullable=True, server_default="0")
        )

    # Derive slug from name for existing rows
    op.execute(
        "UPDATE source_types SET slug = LOWER(REPLACE(REPLACE(REPLACE(name, ' ', '-'), '_', '-'), '.', '-'))"
        " WHERE slug IS NULL"
    )
    # Assign sort_order based on id (preserves creation-time ordering)
    op.execute("UPDATE source_types SET sort_order = id WHERE sort_order IS NULL")

    with op.batch_alter_table("source_types") as batch_op:
        batch_op.alter_column("slug", nullable=False)
        batch_op.alter_column("sort_order", nullable=False, server_default="0")
        batch_op.create_unique_constraint("uq_source_types_slug", ["slug"])


def downgrade() -> None:
    with op.batch_alter_table("source_types") as batch_op:
        batch_op.drop_constraint("uq_source_types_slug", type_="unique")
        batch_op.drop_column("sort_order")
        batch_op.drop_column("slug")
