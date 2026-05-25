from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.domain.programs import program_attention_state


def test_active_program_older_than_seven_days_needs_attention() -> None:
    now = datetime(2026, 5, 25, tzinfo=timezone.utc)
    program = SimpleNamespace(status="active", updated_at=now - timedelta(days=8))

    assert program_attention_state(program, now=now) == "Needs attention"


def test_paused_program_attention_state() -> None:
    now = datetime(2026, 5, 25, tzinfo=timezone.utc)
    program = SimpleNamespace(status="paused", updated_at=now - timedelta(days=30))

    assert program_attention_state(program, now=now) == "Paused"


def test_archived_program_attention_state() -> None:
    now = datetime(2026, 5, 25, tzinfo=timezone.utc)
    program = SimpleNamespace(status="archived", updated_at=now - timedelta(days=30))

    assert program_attention_state(program, now=now) == "Archived"


def test_recent_or_completed_program_attention_state_is_ok() -> None:
    now = datetime(2026, 5, 25, tzinfo=timezone.utc)
    active_program = SimpleNamespace(status="active", updated_at=now - timedelta(days=2))
    completed_program = SimpleNamespace(status="completed", updated_at=now - timedelta(days=30))

    assert program_attention_state(active_program, now=now) == "OK"
    assert program_attention_state(completed_program, now=now) == "OK"
