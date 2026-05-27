"""add report_title to status_reports

Revision ID: 20260527_0021
Revises: 20260527_0020
Create Date: 2026-05-27

Adds report_title (nullable TEXT) to status_reports. Generated on creation
as "Week {ISO_WEEK} {program.name} Report". Existing rows are left NULL and
will display their display_id as a fallback.
"""

import sqlalchemy as sa
from alembic import op

revision: str = "20260527_0021"
down_revision: str = "20260527_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("status_reports", sa.Column("report_title", sa.String(200), nullable=True))


def downgrade() -> None:
    op.drop_column("status_reports", "report_title")
