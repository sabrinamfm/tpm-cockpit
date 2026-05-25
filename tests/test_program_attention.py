from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

from app.domain.programs import program_attention_state, work_item_is_overdue


def test_program_needs_attention_when_any_work_item_is_blocked() -> None:
    now = datetime(2026, 5, 25, tzinfo=timezone.utc)
    program = SimpleNamespace(
        status="active",
        updated_at=now,
        work_items=[
            SimpleNamespace(status="open", due_date=None),
            SimpleNamespace(status="blocked", due_date=None),
        ],
    )

    assert program_attention_state(program, now=now) == "Needs attention"


def test_program_needs_attention_when_any_open_work_item_is_overdue() -> None:
    now = datetime(2026, 5, 25, tzinfo=timezone.utc)
    program = SimpleNamespace(
        status="active",
        updated_at=now,
        work_items=[
            SimpleNamespace(status="open", due_date=date(2026, 5, 20)),
        ],
    )

    assert program_attention_state(program, now=now) == "Needs attention"


def test_program_attention_state_is_ok_without_blocked_or_overdue_work() -> None:
    now = datetime(2026, 5, 25, tzinfo=timezone.utc)
    program = SimpleNamespace(
        status="active",
        updated_at=now - timedelta(days=30),
        work_items=[
            SimpleNamespace(status="open", due_date=date(2026, 5, 30)),
            SimpleNamespace(status="completed", due_date=date(2026, 5, 20)),
        ],
    )

    assert program_attention_state(program, now=now) == "OK"


def test_completed_or_cancelled_work_items_are_not_overdue() -> None:
    today = date(2026, 5, 25)
    completed = SimpleNamespace(status="completed", due_date=date(2026, 5, 20))
    cancelled = SimpleNamespace(status="cancelled", due_date=date(2026, 5, 20))
    open_item = SimpleNamespace(status="open", due_date=date(2026, 5, 20))

    assert work_item_is_overdue(completed, today=today) is False
    assert work_item_is_overdue(cancelled, today=today) is False
    assert work_item_is_overdue(open_item, today=today) is True
