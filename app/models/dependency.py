from datetime import date, datetime
from typing import Optional

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Dependency(Base):
    __tablename__ = "dependencies"
    __table_args__ = (
        CheckConstraint(
            "dependency_type in ('team', 'approval', 'infrastructure', 'release', 'vendor', 'legal', 'finance', 'security', 'product', 'technical', 'operational')",
            name="ck_dependencies_type_allowed",
        ),
        CheckConstraint(
            "status in ('open', 'in_progress', 'confirmed', 'blocked', 'resolved', 'cancelled')",
            name="ck_dependencies_status_allowed",
        ),
        CheckConstraint(
            "blocking_level in ('low', 'medium', 'high', 'critical')",
            name="ck_dependencies_blocking_level_allowed",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    display_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, unique=True, index=True)
    program_id: Mapped[int] = mapped_column(
        ForeignKey("programs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    dependency_type: Mapped[str] = mapped_column(String(50), nullable=False)
    owner: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    external_team: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="open")
    blocking_level: Mapped[str] = mapped_column(String(50), nullable=False, default="medium")
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    last_confirmation_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
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

    program = relationship("Program", back_populates="dependencies")
