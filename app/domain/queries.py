from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.domain.attention import DEPENDENCY_STALE_DAYS, RISK_STALE_DAYS, WORK_ITEM_STALE_DAYS
from app.models.dependency import Dependency
from app.models.program import Program
from app.models.program_status import ProgramStatus
from app.models.risk import Risk
from app.models.work_item import WorkItem


def _operational_program_ids():
    """Subquery: IDs of programs whose status is operational."""
    return select(Program.id).where(
        Program.status_id.in_(select(ProgramStatus.id).where(ProgramStatus.is_operational.is_(True)))
    )

_TERMINAL_WORK = ("completed", "cancelled")
_TERMINAL_DEP = ("resolved", "cancelled")
_TERMINAL_RISK = ("resolved", "accepted")


def get_blocked_work_items(db: Session) -> list[WorkItem]:
    return list(
        db.scalars(
            select(WorkItem)
            .options(selectinload(WorkItem.program))
            .where(
                WorkItem.program_id.in_(_operational_program_ids()),
                WorkItem.status == "blocked",
            )
            .order_by(WorkItem.updated_at.asc())
        )
    )


def get_overdue_work_items(db: Session, today: Optional[date] = None) -> list[WorkItem]:
    cutoff = today or date.today()
    return list(
        db.scalars(
            select(WorkItem)
            .options(selectinload(WorkItem.program))
            .where(
                WorkItem.program_id.in_(_operational_program_ids()),
                WorkItem.due_date.is_not(None),
                WorkItem.due_date < cutoff,
                WorkItem.status.not_in(_TERMINAL_WORK),
            )
            .order_by(WorkItem.due_date.asc())
        )
    )


def get_stale_work_items(db: Session, now: Optional[datetime] = None) -> list[WorkItem]:
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=WORK_ITEM_STALE_DAYS)
    return list(
        db.scalars(
            select(WorkItem)
            .options(selectinload(WorkItem.program))
            .where(
                WorkItem.program_id.in_(_operational_program_ids()),
                WorkItem.updated_at < cutoff,
                WorkItem.status.not_in(_TERMINAL_WORK),
            )
            .order_by(WorkItem.updated_at.asc())
        )
    )


def get_blocked_dependencies(db: Session) -> list[Dependency]:
    return list(
        db.scalars(
            select(Dependency)
            .options(selectinload(Dependency.program))
            .where(
                Dependency.program_id.in_(_operational_program_ids()),
                Dependency.status == "blocked",
            )
            .order_by(Dependency.updated_at.asc())
        )
    )


def get_critical_dependencies(db: Session) -> list[Dependency]:
    return list(
        db.scalars(
            select(Dependency)
            .options(selectinload(Dependency.program))
            .where(
                Dependency.program_id.in_(_operational_program_ids()),
                Dependency.blocking_level == "critical",
                Dependency.status.not_in(_TERMINAL_DEP),
            )
            .order_by(Dependency.updated_at.desc())
        )
    )


def get_stale_dependencies(db: Session, now: Optional[datetime] = None) -> list[Dependency]:
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=DEPENDENCY_STALE_DAYS)
    return list(
        db.scalars(
            select(Dependency)
            .options(selectinload(Dependency.program))
            .where(
                Dependency.program_id.in_(_operational_program_ids()),
                Dependency.last_confirmation_at.is_not(None),
                Dependency.last_confirmation_at < cutoff,
                Dependency.status.not_in(_TERMINAL_DEP),
            )
            .order_by(Dependency.last_confirmation_at.asc())
        )
    )


def get_critical_risks(db: Session) -> list[Risk]:
    return list(
        db.scalars(
            select(Risk)
            .options(selectinload(Risk.program))
            .where(
                Risk.program_id.in_(_operational_program_ids()),
                Risk.severity.in_(("high", "critical")),
                Risk.status.not_in(_TERMINAL_RISK),
            )
            .order_by(Risk.updated_at.desc())
        )
    )


def get_stale_risks(db: Session, now: Optional[datetime] = None) -> list[Risk]:
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=RISK_STALE_DAYS)
    return list(
        db.scalars(
            select(Risk)
            .options(selectinload(Risk.program))
            .where(
                Risk.program_id.in_(_operational_program_ids()),
                Risk.last_reviewed_at.is_not(None),
                Risk.last_reviewed_at < cutoff,
                Risk.status.not_in(_TERMINAL_RISK),
            )
            .order_by(Risk.last_reviewed_at.asc())
        )
    )


def get_programs_needing_attention(
    db: Session,
    today: Optional[date] = None,
    now: Optional[datetime] = None,
) -> list[Program]:
    today = today or date.today()
    stale_cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=DEPENDENCY_STALE_DAYS)

    blocked_prog_ids = select(WorkItem.program_id).where(WorkItem.status == "blocked")
    overdue_prog_ids = select(WorkItem.program_id).where(
        WorkItem.due_date.is_not(None),
        WorkItem.due_date < today,
        WorkItem.status.not_in(_TERMINAL_WORK),
    )
    stale_dep_prog_ids = select(Dependency.program_id).where(
        Dependency.last_confirmation_at.is_not(None),
        Dependency.last_confirmation_at < stale_cutoff,
        Dependency.status.not_in(_TERMINAL_DEP),
    )

    return list(
        db.scalars(
            select(Program)
            .where(
                Program.status_id.in_(
                    select(ProgramStatus.id).where(ProgramStatus.is_operational.is_(True))
                ),
                or_(
                    Program.id.in_(blocked_prog_ids),
                    Program.id.in_(overdue_prog_ids),
                    Program.id.in_(stale_dep_prog_ids),
                ),
            )
            .order_by(Program.updated_at.desc())
        )
    )


def get_recently_updated_programs(db: Session, limit: int = 10) -> list[Program]:
    return list(
        db.scalars(
            select(Program)
            .order_by(Program.updated_at.desc())
            .limit(limit)
        )
    )
