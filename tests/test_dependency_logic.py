from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.domain.dependencies import dependency_is_stale


def test_dependency_is_stale_when_confirmation_is_older_than_fourteen_days() -> None:
    now = datetime(2026, 5, 25, tzinfo=timezone.utc)
    dependency = SimpleNamespace(
        status="open",
        last_confirmation_at=now - timedelta(days=15),
    )

    assert dependency_is_stale(dependency, now=now) is True


def test_resolved_or_cancelled_dependencies_are_not_stale() -> None:
    now = datetime(2026, 5, 25, tzinfo=timezone.utc)
    resolved = SimpleNamespace(status="resolved", last_confirmation_at=now - timedelta(days=30))
    cancelled = SimpleNamespace(status="cancelled", last_confirmation_at=now - timedelta(days=30))

    assert dependency_is_stale(resolved, now=now) is False
    assert dependency_is_stale(cancelled, now=now) is False


def test_dependency_without_confirmation_is_not_stale() -> None:
    dependency = SimpleNamespace(status="open", last_confirmation_at=None)

    assert dependency_is_stale(dependency) is False
