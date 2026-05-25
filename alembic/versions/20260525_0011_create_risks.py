"""create risks table

Revision ID: 20260525_0011
Revises: 20260525_0010
Create Date: 2026-05-25
"""

import sqlalchemy as sa
from alembic import op

revision: str = "20260525_0011"
down_revision: str = "20260525_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "risks",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column(
            "program_id",
            sa.Integer,
            sa.ForeignKey("programs.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("severity", sa.String(50), nullable=False, server_default="medium"),
        sa.Column("likelihood", sa.String(50), nullable=False, server_default="possible"),
        sa.Column("status", sa.String(50), nullable=False, server_default="open"),
        sa.Column("owner", sa.String(120), nullable=True),
        sa.Column("mitigation", sa.Text, nullable=True),
        sa.Column("target_resolution_date", sa.Date, nullable=True),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
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
            "severity in ('low', 'medium', 'high', 'critical')",
            name="ck_risks_severity_allowed",
        ),
        sa.CheckConstraint(
            "likelihood in ('unlikely', 'possible', 'likely', 'very_likely')",
            name="ck_risks_likelihood_allowed",
        ),
        sa.CheckConstraint(
            "status in ('open', 'monitoring', 'mitigated', 'resolved', 'accepted')",
            name="ck_risks_status_allowed",
        ),
    )


def downgrade() -> None:
    op.drop_table("risks")
