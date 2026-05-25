from datetime import date, datetime, timezone
from typing import Optional, Protocol


class WorkItemLike(Protocol):
    status: str
    due_date: Optional[date]


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


def program_attention_state(program: ProgramLike, now: Optional[datetime] = None) -> str:
    current_date = (now or datetime.now(timezone.utc)).date()
    if any(work_item.status == "blocked" for work_item in program.work_items):
        return "Needs attention"
    if any(work_item_is_overdue(work_item, today=current_date) for work_item in program.work_items):
        return "Needs attention"

    return "OK"
