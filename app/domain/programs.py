from datetime import datetime, timedelta, timezone
from typing import Optional, Protocol


class ProgramLike(Protocol):
    status: str
    updated_at: datetime


def program_attention_state(program: ProgramLike, now: Optional[datetime] = None) -> str:
    if program.status == "paused":
        return "Paused"
    if program.status == "archived":
        return "Archived"

    current_time = now or datetime.now(timezone.utc)
    updated_at = program.updated_at
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)

    if program.status == "active" and updated_at < current_time - timedelta(days=7):
        return "Needs attention"

    return "OK"
