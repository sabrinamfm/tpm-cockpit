from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.program_status import ProgramStatus
    from app.models.status_report import StatusReport


class Program(Base):
    __tablename__ = "programs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status_id: Mapped[int] = mapped_column(
        ForeignKey("program_statuses.id", ondelete="RESTRICT"), nullable=False
    )
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

    program_status: Mapped["ProgramStatus"] = relationship(
        "ProgramStatus",
        back_populates="programs",
        lazy="joined",
    )
    work_items: Mapped[list["WorkItem"]] = relationship(
        "WorkItem",
        back_populates="program",
        cascade="all, delete-orphan",
    )
    dependencies: Mapped[list["Dependency"]] = relationship(
        "Dependency",
        back_populates="program",
        cascade="all, delete-orphan",
    )
    risks: Mapped[list["Risk"]] = relationship(
        "Risk",
        back_populates="program",
        cascade="all, delete-orphan",
    )
    status_reports: Mapped[list["StatusReport"]] = relationship(
        "StatusReport",
        back_populates="program",
        cascade="all, delete-orphan",
    )

    @property
    def status(self) -> str:
        """Slug of the current program status. Kept for API/template backward compat."""
        return self.program_status.slug if self.program_status else ""
