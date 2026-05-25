"""create program_statuses table and seed defaults

Revision ID: 20260525_0007
Revises: 20260525_0006
Create Date: 2026-05-25 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260525_0007"
down_revision: Union[str, None] = "20260525_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "program_statuses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("slug", sa.String(50), nullable=False),
        sa.Column("color", sa.String(20), nullable=False, server_default="#6b7280"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("slug", name="uq_program_statuses_slug"),
    )

    # Seed defaults — idempotent per slug
    conn = op.get_bind()
    defaults = [
        ("Active", "active", "#16a34a", 1, 1, 1),
        ("Paused", "paused", "#d97706", 2, 1, 0),
        ("Completed", "completed", "#2364aa", 3, 1, 0),
        ("Archived", "archived", "#6b7280", 4, 1, 0),
    ]
    for name, slug, color, sort_order, is_active, is_default in defaults:
        conn.execute(
            sa.text(
                "INSERT INTO program_statuses (name, slug, color, sort_order, is_active, is_default)"
                " SELECT :name, :slug, :color, :sort_order, :is_active, :is_default"
                " WHERE NOT EXISTS (SELECT 1 FROM program_statuses WHERE slug = :slug)"
            ),
            {
                "name": name,
                "slug": slug,
                "color": color,
                "sort_order": sort_order,
                "is_active": is_active,
                "is_default": is_default,
            },
        )


def downgrade() -> None:
    op.drop_table("program_statuses")
