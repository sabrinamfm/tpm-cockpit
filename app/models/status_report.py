from datetime import date, datetime
from typing import Optional

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class StatusReport(Base):
    __tablename__ = "status_reports"
    __table_args__ = (
        CheckConstraint(
            "reported_health in ('on_track', 'at_risk', 'off_track')",
            name="ck_status_reports_reported_health_allowed",
        ),
        CheckConstraint(
            "suggested_health in ('on_track', 'at_risk', 'off_track')",
            name="ck_status_reports_suggested_health_allowed",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    display_id: Mapped[str] = mapped_column(String(20), nullable=False, unique=True, index=True)
    program_id: Mapped[int] = mapped_column(
        ForeignKey("programs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    reported_health: Mapped[str] = mapped_column(String(20), nullable=False)
    suggested_health: Mapped[str] = mapped_column(String(20), nullable=False)
    health_rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    program = relationship("Program", back_populates="status_reports")
