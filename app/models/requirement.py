from datetime import date, datetime
from typing import Optional

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Requirement(Base):
    __tablename__ = "requirements"
    __table_args__ = (
        CheckConstraint(
            "source_type in ('okr', 'change_management', 'customer_commitment', 'compliance',"
            " 'leadership_request', 'strategic_initiative', 'operational_requirement', 'other')",
            name="ck_requirements_source_type_allowed",
        ),
        CheckConstraint(
            "status in ('proposed', 'accepted', 'in_progress', 'delivered', 'deferred', 'cancelled')",
            name="ck_requirements_status_allowed",
        ),
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
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, default="other")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="proposed")
    owner: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    target_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    link: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    program = relationship("Program", back_populates="requirements")
