from datetime import date, datetime, timedelta, timezone
from typing import Optional, Protocol

WORK_ITEM_STALE_DAYS = 7
DEPENDENCY_STALE_DAYS = 14


class WorkItemLike(Protocol):
    status: str
    due_date: Optional[date]
    updated_at: datetime


class DependencyLike(Protocol):
    status: str
    last_confirmation_at: Optional[datetime]


class ProgramLike(Protocol):
    work_items: list[WorkItemLike]
    dependencies: list[DependencyLike]


def work_item_is_overdue(item: WorkItemLike, today: Optional[date] = None) -> bool:
    if item.due_date is None:
        return False
    if item.status in ("completed", "cancelled"):
        return False
    return item.due_date < (today or date.today())


def work_item_is_stale(item: WorkItemLike, now: Optional[datetime] = None) -> bool:
    if item.status in ("completed", "cancelled"):
        return False
    current = now or datetime.now(timezone.utc)
    updated_at = item.updated_at
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    return updated_at < current - timedelta(days=WORK_ITEM_STALE_DAYS)


def dependency_is_stale(dep: DependencyLike, now: Optional[datetime] = None) -> bool:
    if dep.status in ("resolved", "cancelled"):
        return False
    if dep.last_confirmation_at is None:
        return False
    current = now or datetime.now(timezone.utc)
    last_confirmed = dep.last_confirmation_at
    if last_confirmed.tzinfo is None:
        last_confirmed = last_confirmed.replace(tzinfo=timezone.utc)
    return last_confirmed < current - timedelta(days=DEPENDENCY_STALE_DAYS)


def program_needs_attention(program: ProgramLike, now: Optional[datetime] = None) -> bool:
    current_date = (now or datetime.now(timezone.utc)).date()
    if any(item.status == "blocked" for item in program.work_items):
        return True
    if any(work_item_is_overdue(item, today=current_date) for item in program.work_items):
        return True
    if any(dependency_is_stale(dep, now=now) for dep in program.dependencies):
        return True
    return False
