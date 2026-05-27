from datetime import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

_OBJECT_TYPES_SQL = "'work_item', 'dependency', 'risk', 'status_report', 'milestone', 'decision', 'requirement'"
_REL_TYPES_SQL = (
    "'relates_to', 'blocks', 'blocked_by', 'mitigates', "
    "'tracks', 'highlights', 'duplicates', 'depends_on'"
)


class Relationship(Base):
    __tablename__ = "relationships"
    __table_args__ = (
        CheckConstraint(
            f"source_type in ({_OBJECT_TYPES_SQL})",
            name="ck_relationships_source_type",
        ),
        CheckConstraint(
            f"target_type in ({_OBJECT_TYPES_SQL})",
            name="ck_relationships_target_type",
        ),
        CheckConstraint(
            f"relationship_type in ({_REL_TYPES_SQL})",
            name="ck_relationships_type",
        ),
        CheckConstraint(
            "NOT (source_type = target_type AND source_id = target_id)",
            name="ck_relationships_no_self",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    display_id: Mapped[str] = mapped_column(String(20), nullable=False, unique=True, index=True)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    relationship_type: Mapped[str] = mapped_column(String(20), nullable=False)
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)
    target_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
