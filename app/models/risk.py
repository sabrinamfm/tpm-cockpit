from datetime import date, datetime
from typing import Optional

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Risk(Base):
    __tablename__ = "risks"
    __table_args__ = (
        CheckConstraint(
            "severity in ('low', 'medium', 'high', 'critical')",
            name="ck_risks_severity_allowed",
        ),
        CheckConstraint(
            "likelihood in ('unlikely', 'possible', 'likely', 'very_likely')",
            name="ck_risks_likelihood_allowed",
        ),
        CheckConstraint(
            "status in ('open', 'monitoring', 'mitigated', 'resolved', 'accepted')",
            name="ck_risks_status_allowed",
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
    severity: Mapped[str] = mapped_column(String(50), nullable=False, default="medium")
    likelihood: Mapped[str] = mapped_column(String(50), nullable=False, default="possible")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="open")
    owner: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    mitigation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    target_resolution_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    last_reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
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

    program = relationship("Program", back_populates="risks")
