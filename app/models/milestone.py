from datetime import date, datetime
from typing import Optional

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Milestone(Base):
    __tablename__ = "milestones"
    __table_args__ = (
        CheckConstraint(
            "status in ('planned', 'on_track', 'at_risk', 'off_track', 'blocked', 'achieved', 'cancelled')",
            name="ck_milestones_status_allowed",
        ),
        # Future governance rule (not yet enforced in code):
        # A milestone with status 'at_risk' or 'off_track' should have at least one
        # supporting relationship that provides evidence for that assessment.
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    display_id: Mapped[str] = mapped_column(String(20), nullable=False, unique=True, index=True)
    program_id: Mapped[int] = mapped_column(
        ForeignKey("programs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    target_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="planned")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    program = relationship("Program", back_populates="milestones")
