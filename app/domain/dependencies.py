from datetime import datetime, timedelta, timezone
from typing import Optional, Protocol


class DependencyLike(Protocol):
    status: str
    last_confirmation_at: Optional[datetime]


def dependency_is_stale(dependency: DependencyLike, now: Optional[datetime] = None) -> bool:
    if dependency.status in ("resolved", "cancelled"):
        return False
    if dependency.last_confirmation_at is None:
        return False

    current_time = now or datetime.now(timezone.utc)
    last_confirmation_at = dependency.last_confirmation_at
    if last_confirmation_at.tzinfo is None:
        last_confirmation_at = last_confirmation_at.replace(tzinfo=timezone.utc)
    return last_confirmation_at < current_time - timedelta(days=14)
