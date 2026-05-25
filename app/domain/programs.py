from datetime import date, datetime, timedelta, timezone
from typing import Optional, Protocol


class WorkItemLike(Protocol):
    status: str
    due_date: Optional[date]
    updated_at: datetime


class ProgramLike(Protocol):
    status: str
    updated_at: datetime
    work_items: list[WorkItemLike]


def work_item_is_overdue(work_item: WorkItemLike, today: Optional[date] = None) -> bool:
    if work_item.due_date is None:
        return False
    if work_item.status in ("completed", "cancelled"):
        return False
    return work_item.due_date < (today or date.today())


def work_item_is_stale(work_item: WorkItemLike, now: Optional[datetime] = None) -> bool:
    if work_item.status in ("completed", "cancelled"):
        return False
    current_time = now or datetime.now(timezone.utc)
    updated_at = work_item.updated_at
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    return updated_at < current_time - timedelta(days=7)


def program_attention_state(program: ProgramLike, now: Optional[datetime] = None) -> str:
    current_date = (now or datetime.now(timezone.utc)).date()
    if any(work_item.status == "blocked" for work_item in program.work_items):
        return "Needs attention"
    if any(work_item_is_overdue(work_item, today=current_date) for work_item in program.work_items):
        return "Needs attention"

    return "OK"
