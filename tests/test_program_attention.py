from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

from app.domain.attention import work_item_is_overdue, work_item_is_stale
from app.domain.programs import program_attention_state

_operational = SimpleNamespace(is_operational=True)
_inactive = SimpleNamespace(is_operational=False)


def test_program_needs_attention_when_any_work_item_is_blocked() -> None:
    now = datetime(2026, 5, 25, tzinfo=timezone.utc)
    program = SimpleNamespace(
        work_items=[
            SimpleNamespace(status="open", due_date=None),
            SimpleNamespace(status="blocked", due_date=None),
        ],
        dependencies=[],
        program_status=_operational,
    )

    assert program_attention_state(program, now=now) == "Needs attention"


def test_program_needs_attention_when_any_open_work_item_is_overdue() -> None:
    now = datetime(2026, 5, 25, tzinfo=timezone.utc)
    program = SimpleNamespace(
        work_items=[
            SimpleNamespace(status="open", due_date=date(2026, 5, 20)),
        ],
        dependencies=[],
        program_status=_operational,
    )

    assert program_attention_state(program, now=now) == "Needs attention"


def test_program_needs_attention_when_dependency_is_stale() -> None:
    now = datetime(2026, 5, 25, tzinfo=timezone.utc)
    program = SimpleNamespace(
        work_items=[],
        dependencies=[
            SimpleNamespace(status="open", last_confirmation_at=now - timedelta(days=15)),
        ],
        program_status=_operational,
    )

    assert program_attention_state(program, now=now) == "Needs attention"


def test_program_attention_state_is_ok_without_blocked_overdue_or_stale_dep() -> None:
    now = datetime(2026, 5, 25, tzinfo=timezone.utc)
    program = SimpleNamespace(
        work_items=[
            SimpleNamespace(status="open", due_date=date(2026, 5, 30)),
            SimpleNamespace(status="completed", due_date=date(2026, 5, 20)),
        ],
        dependencies=[
            SimpleNamespace(status="open", last_confirmation_at=now - timedelta(days=3)),
        ],
        program_status=_operational,
    )

    assert program_attention_state(program, now=now) == "OK"


def test_non_operational_program_returns_inactive() -> None:
    now = datetime(2026, 5, 25, tzinfo=timezone.utc)
    program = SimpleNamespace(
        work_items=[SimpleNamespace(status="blocked", due_date=None)],
        dependencies=[],
        program_status=_inactive,
    )

    assert program_attention_state(program, now=now) == "Inactive"


def test_non_operational_program_never_needs_attention() -> None:
    now = datetime(2026, 5, 25, tzinfo=timezone.utc)
    program = SimpleNamespace(
        work_items=[
            SimpleNamespace(status="blocked", due_date=None),
            SimpleNamespace(status="open", due_date=date(2026, 5, 1)),
        ],
        dependencies=[
            SimpleNamespace(status="open", last_confirmation_at=now - timedelta(days=30)),
        ],
        program_status=_inactive,
    )

    assert program_attention_state(program, now=now) == "Inactive"


def test_completed_or_cancelled_work_items_are_not_overdue() -> None:
    today = date(2026, 5, 25)
    completed = SimpleNamespace(status="completed", due_date=date(2026, 5, 20))
    cancelled = SimpleNamespace(status="cancelled", due_date=date(2026, 5, 20))
    open_item = SimpleNamespace(status="open", due_date=date(2026, 5, 20))

    assert work_item_is_overdue(completed, today=today) is False
    assert work_item_is_overdue(cancelled, today=today) is False
    assert work_item_is_overdue(open_item, today=today) is True


def test_open_work_item_is_stale_when_updated_more_than_seven_days_ago() -> None:
    now = datetime(2026, 5, 25, tzinfo=timezone.utc)
    stale_item = SimpleNamespace(status="open", due_date=None, updated_at=now - timedelta(days=8))
    fresh_item = SimpleNamespace(status="open", due_date=None, updated_at=now - timedelta(days=2))
    completed_item = SimpleNamespace(status="completed", due_date=None, updated_at=now - timedelta(days=30))

    assert work_item_is_stale(stale_item, now=now) is True
    assert work_item_is_stale(fresh_item, now=now) is False
    assert work_item_is_stale(completed_item, now=now) is False
