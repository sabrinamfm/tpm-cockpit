"""create relationships table

Revision ID: 20260527_0015
Revises: 20260526_0014
Create Date: 2026-05-27

Polymorphic join table linking any two core objects (work_item, dependency,
risk, status_report). Source and target are stored as (type, id) pairs with
no FK constraints — existence is enforced at the application layer.
"""

import sqlalchemy as sa
from alembic import op

revision: str = "20260527_0015"
down_revision: str = "20260526_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "relationships",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("display_id", sa.String(20), nullable=False),
        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("source_id", sa.Integer, nullable=False),
        sa.Column("relationship_type", sa.String(20), nullable=False),
        sa.Column("target_type", sa.String(20), nullable=False),
        sa.Column("target_id", sa.Integer, nullable=False),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
        ),
        sa.CheckConstraint(
            "source_type in ('work_item', 'dependency', 'risk', 'status_report')",
            name="ck_relationships_source_type",
        ),
        sa.CheckConstraint(
            "target_type in ('work_item', 'dependency', 'risk', 'status_report')",
            name="ck_relationships_target_type",
        ),
        sa.CheckConstraint(
            "relationship_type in ('relates_to', 'blocks', 'blocked_by', 'mitigates',"
            " 'tracks', 'highlights', 'duplicates', 'depends_on')",
            name="ck_relationships_type",
        ),
        sa.CheckConstraint(
            "NOT (source_type = target_type AND source_id = target_id)",
            name="ck_relationships_no_self",
        ),
    )
    op.create_index("ix_relationships_display_id", "relationships", ["display_id"], unique=True)
    op.create_index("ix_relationships_source", "relationships", ["source_type", "source_id"])
    op.create_index("ix_relationships_target", "relationships", ["target_type", "target_id"])


def downgrade() -> None:
    op.drop_index("ix_relationships_target", table_name="relationships")
    op.drop_index("ix_relationships_source", table_name="relationships")
    op.drop_index("ix_relationships_display_id", table_name="relationships")
    op.drop_table("relationships")
