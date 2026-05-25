from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

DEFAULT_PROGRAM_STATUSES = [
    {"name": "Active", "slug": "active", "color": "#16a34a", "sort_order": 1, "is_active": True, "is_default": True},
    {"name": "Paused", "slug": "paused", "color": "#d97706", "sort_order": 2, "is_active": True, "is_default": False},
    {"name": "Completed", "slug": "completed", "color": "#2364aa", "sort_order": 3, "is_active": True, "is_default": False},
    {"name": "Archived", "slug": "archived", "color": "#6b7280", "sort_order": 4, "is_active": True, "is_default": False},
]


class ProgramStatus(Base):
    __tablename__ = "program_statuses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    color: Mapped[str] = mapped_column(String(20), nullable=False, default="#6b7280", server_default="#6b7280")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    programs: Mapped[list["Program"]] = relationship(
        "Program", back_populates="program_status", passive_deletes=True
    )


def seed_default_program_statuses(db) -> None:
    """Insert defaults once, on first run only (when the table is empty)."""
    from sqlalchemy import func, select

    count = db.scalar(select(func.count(ProgramStatus.id))) or 0
    if count > 0:
        return
    for data in DEFAULT_PROGRAM_STATUSES:
        db.add(ProgramStatus(**data))
    db.commit()
