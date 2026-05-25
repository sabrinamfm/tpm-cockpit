"""migrate programs.status string to status_id FK

Revision ID: 20260525_0008
Revises: 20260525_0007
Create Date: 2026-05-25 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260525_0008"
down_revision: Union[str, None] = "20260525_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Step 1: add nullable status_id column
    with op.batch_alter_table("programs") as batch_op:
        batch_op.add_column(sa.Column("status_id", sa.Integer(), nullable=True))

    # Step 2: populate status_id from existing status slug
    rows = conn.execute(sa.text("SELECT id, slug FROM program_statuses")).fetchall()
    slug_to_id = {row[1]: row[0] for row in rows}

    for slug, sid in slug_to_id.items():
        conn.execute(
            sa.text("UPDATE programs SET status_id = :sid WHERE status = :slug"),
            {"sid": sid, "slug": slug},
        )

    # Fallback: any remaining nulls get the default status (is_default=1), else first
    default_row = conn.execute(
        sa.text("SELECT id FROM program_statuses WHERE is_default = 1 ORDER BY sort_order LIMIT 1")
    ).fetchone()
    if default_row is None and rows:
        default_row = conn.execute(
            sa.text("SELECT id FROM program_statuses ORDER BY sort_order LIMIT 1")
        ).fetchone()
    if default_row:
        conn.execute(
            sa.text("UPDATE programs SET status_id = :sid WHERE status_id IS NULL"),
            {"sid": default_row[0]},
        )

    # Step 3: drop old status column, make status_id NOT NULL, add FK constraint
    with op.batch_alter_table("programs") as batch_op:
        batch_op.drop_constraint("ck_programs_status_allowed", type_="check")
        batch_op.drop_column("status")
        batch_op.alter_column("status_id", existing_type=sa.Integer(), nullable=False)
        batch_op.create_foreign_key(
            "fk_programs_status_id",
            "program_statuses",
            ["status_id"],
            ["id"],
        )


def downgrade() -> None:
    conn = op.get_bind()

    # Step 1: re-add status string column as nullable
    with op.batch_alter_table("programs") as batch_op:
        batch_op.drop_constraint("fk_programs_status_id", type_="foreignkey")
        batch_op.add_column(sa.Column("status", sa.String(50), nullable=True))

    # Step 2: populate status from status_id via join
    conn.execute(
        sa.text(
            "UPDATE programs SET status = ("
            "  SELECT slug FROM program_statuses WHERE id = programs.status_id"
            ")"
        )
    )
    # Fallback for any nulls
    conn.execute(
        sa.text("UPDATE programs SET status = 'active' WHERE status IS NULL")
    )

    # Step 3: make status NOT NULL, add CHECK constraint, drop status_id
    with op.batch_alter_table("programs") as batch_op:
        batch_op.alter_column("status", existing_type=sa.String(50), nullable=False, server_default="active")
        batch_op.create_check_constraint(
            "ck_programs_status_allowed",
            "status in ('active', 'paused', 'completed', 'archived')",
        )
        batch_op.drop_column("status_id")
