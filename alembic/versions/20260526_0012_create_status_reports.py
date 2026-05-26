"""create status_reports table

Revision ID: 20260526_0012
Revises: 20260525_0011
Create Date: 2026-05-26
"""

import sqlalchemy as sa
from alembic import op

revision: str = "20260526_0012"
down_revision: str = "20260525_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "status_reports",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column(
            "program_id",
            sa.Integer,
            sa.ForeignKey("programs.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("report_date", sa.Date, nullable=False),
        sa.Column("reported_health", sa.String(20), nullable=False),
        sa.Column("suggested_health", sa.String(20), nullable=False),
        sa.Column("health_rationale", sa.Text, nullable=True),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "reported_health in ('on_track', 'at_risk', 'off_track')",
            name="ck_status_reports_reported_health_allowed",
        ),
        sa.CheckConstraint(
            "suggested_health in ('on_track', 'at_risk', 'off_track')",
            name="ck_status_reports_suggested_health_allowed",
        ),
    )


def downgrade() -> None:
    op.drop_table("status_reports")
