"""add suggested_state to status_reports

Revision ID: 20260528_0022
Revises: 20260527_0021
Create Date: 2026-05-28

Adds suggested_state (nullable String(20)) to status_reports. Stores the
full 5-state program health signal (inactive, on_track, needs_attention,
at_risk, off_track) computed at report creation, preserving information that
the existing suggested_health 3-state mapping discards. Existing rows are
left NULL; no backfill is attempted.
"""

import sqlalchemy as sa
from alembic import op

revision: str = "20260528_0022"
down_revision: str = "20260527_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "status_reports",
        sa.Column("suggested_state", sa.String(20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("status_reports", "suggested_state")
