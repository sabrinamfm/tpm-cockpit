from datetime import date, datetime
from typing import Optional

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class WorkItem(Base):
    __tablename__ = "work_items"
    __table_args__ = (
        CheckConstraint(
            "status in ('open', 'in_progress', 'blocked', 'completed', 'cancelled')",
            name="ck_work_items_status_allowed",
        ),
        CheckConstraint(
            "priority in ('low', 'medium', 'high', 'critical')",
            name="ck_work_items_priority_allowed",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    program_id: Mapped[int] = mapped_column(
        ForeignKey("programs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="open")
    priority: Mapped[str] = mapped_column(String(50), nullable=False, default="medium")
    owner: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    next_step: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_type_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("source_types.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    link: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    last_touched_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    program = relationship("Program", back_populates="work_items")
    source_type = relationship("SourceType", back_populates="work_items")
