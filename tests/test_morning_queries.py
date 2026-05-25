from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.domain.queries import (
    get_blocked_dependencies,
    get_blocked_work_items,
    get_critical_dependencies,
    get_overdue_work_items,
    get_programs_needing_attention,
    get_recently_updated_programs,
    get_stale_dependencies,
    get_stale_work_items,
)
from app.models.dependency import Dependency
from app.models.program import Program
from app.models.program_status import seed_default_program_statuses
from app.models.work_item import WorkItem


@pytest.fixture
def db(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        seed_default_program_statuses(session)
        yield session
    Base.metadata.drop_all(engine)


def _program(db, name="Test Program", status_slug="active") -> Program:
    status = db.execute(
        text("SELECT id FROM program_statuses WHERE slug = :slug LIMIT 1"),
        {"slug": status_slug},
    ).fetchone()
    p = Program(name=name, status_id=status[0])
    db.add(p)
    db.flush()
    return p


def _work_item(db, program: Program, **kwargs) -> WorkItem:
    defaults = {"title": "Item", "status": "open", "priority": "medium"}
    defaults.update(kwargs)
    wi = WorkItem(program_id=program.id, **defaults)
    db.add(wi)
    db.flush()
    return wi


def _dependency(db, program: Program, **kwargs) -> Dependency:
    defaults = {
        "title": "Dep",
        "dependency_type": "team",
        "status": "open",
        "blocking_level": "medium",
    }
    defaults.update(kwargs)
    dep = Dependency(program_id=program.id, **defaults)
    db.add(dep)
    db.flush()
    return dep


# ── get_blocked_dependencies ─────────────────────────────────────────────────

def test_get_blocked_dependencies_returns_blocked(db) -> None:
    p = _program(db)
    _dependency(db, p, title="Blocked dep", status="blocked")
    _dependency(db, p, title="Open dep", status="open")
    db.commit()

    result = get_blocked_dependencies(db)

    assert len(result) == 1
    assert result[0].title == "Blocked dep"


def test_get_blocked_dependencies_empty(db) -> None:
    p = _program(db)
    _dependency(db, p, status="open")
    db.commit()

    assert get_blocked_dependencies(db) == []


def test_get_blocked_dependencies_does_not_exclude_any_blocking_level(db) -> None:
    p = _program(db)
    _dependency(db, p, title="Low blocked", status="blocked", blocking_level="low")
    _dependency(db, p, title="Critical blocked", status="blocked", blocking_level="critical")
    db.commit()

    result = get_blocked_dependencies(db)

    assert len(result) == 2


# ── get_blocked_work_items ────────────────────────────────────────────────────

def test_get_blocked_work_items_returns_blocked(db) -> None:
    p = _program(db)
    _work_item(db, p, title="Blocked", status="blocked")
    _work_item(db, p, title="Open", status="open")
    db.commit()

    result = get_blocked_work_items(db)

    assert len(result) == 1
    assert result[0].title == "Blocked"


def test_get_blocked_work_items_empty(db) -> None:
    p = _program(db)
    _work_item(db, p, status="open")
    db.commit()

    assert get_blocked_work_items(db) == []


# ── get_overdue_work_items ────────────────────────────────────────────────────

def test_get_overdue_work_items_returns_past_due(db) -> None:
    today = date(2026, 5, 25)
    p = _program(db)
    _work_item(db, p, title="Overdue", status="open", due_date=date(2026, 5, 20))
    _work_item(db, p, title="Future", status="open", due_date=date(2026, 6, 1))
    _work_item(db, p, title="No date", status="open")
    db.commit()

    result = get_overdue_work_items(db, today=today)

    assert len(result) == 1
    assert result[0].title == "Overdue"


def test_get_overdue_work_items_excludes_terminal_statuses(db) -> None:
    today = date(2026, 5, 25)
    p = _program(db)
    _work_item(db, p, status="completed", due_date=date(2026, 5, 20))
    _work_item(db, p, status="cancelled", due_date=date(2026, 5, 20))
    db.commit()

    assert get_overdue_work_items(db, today=today) == []


# ── get_stale_work_items ──────────────────────────────────────────────────────

def test_get_stale_work_items_returns_items_older_than_seven_days(db) -> None:
    now = datetime(2026, 5, 25, 12, 0, tzinfo=timezone.utc)
    p = _program(db)
    stale = _work_item(db, p, title="Stale", status="open")
    stale.updated_at = now - timedelta(days=8)
    fresh = _work_item(db, p, title="Fresh", status="open")
    fresh.updated_at = now - timedelta(days=2)
    db.commit()

    result = get_stale_work_items(db, now=now)

    assert len(result) == 1
    assert result[0].title == "Stale"


def test_get_stale_work_items_excludes_terminal_statuses(db) -> None:
    now = datetime(2026, 5, 25, 12, 0, tzinfo=timezone.utc)
    p = _program(db)
    item = _work_item(db, p, status="completed")
    item.updated_at = now - timedelta(days=30)
    db.commit()

    assert get_stale_work_items(db, now=now) == []


# ── get_critical_dependencies ─────────────────────────────────────────────────

def test_get_critical_dependencies_returns_critical_non_terminal(db) -> None:
    p = _program(db)
    _dependency(db, p, title="Critical open", blocking_level="critical", status="open")
    _dependency(db, p, title="Critical resolved", blocking_level="critical", status="resolved")
    _dependency(db, p, title="High open", blocking_level="high", status="open")
    db.commit()

    result = get_critical_dependencies(db)

    assert len(result) == 1
    assert result[0].title == "Critical open"


def test_get_critical_dependencies_excludes_cancelled(db) -> None:
    p = _program(db)
    _dependency(db, p, blocking_level="critical", status="cancelled")
    db.commit()

    assert get_critical_dependencies(db) == []


# ── get_stale_dependencies ────────────────────────────────────────────────────

def test_get_stale_dependencies_returns_confirmed_long_ago(db) -> None:
    now = datetime(2026, 5, 25, 12, 0, tzinfo=timezone.utc)
    p = _program(db)
    stale = _dependency(db, p, title="Stale dep", status="open")
    stale.last_confirmation_at = now - timedelta(days=15)
    fresh = _dependency(db, p, title="Fresh dep", status="open")
    fresh.last_confirmation_at = now - timedelta(days=3)
    no_conf = _dependency(db, p, title="Never confirmed", status="open")
    no_conf.last_confirmation_at = None
    db.commit()

    result = get_stale_dependencies(db, now=now)

    assert len(result) == 1
    assert result[0].title == "Stale dep"


def test_get_stale_dependencies_excludes_terminal_statuses(db) -> None:
    now = datetime(2026, 5, 25, 12, 0, tzinfo=timezone.utc)
    p = _program(db)
    dep = _dependency(db, p, status="resolved")
    dep.last_confirmation_at = now - timedelta(days=30)
    db.commit()

    assert get_stale_dependencies(db, now=now) == []


def test_get_stale_dependencies_ignores_never_confirmed(db) -> None:
    now = datetime(2026, 5, 25, 12, 0, tzinfo=timezone.utc)
    p = _program(db)
    _dependency(db, p, status="open")
    db.commit()

    assert get_stale_dependencies(db, now=now) == []


# ── get_programs_needing_attention ────────────────────────────────────────────

def test_get_programs_needing_attention_via_blocked_work_item(db) -> None:
    today = date(2026, 5, 25)
    p = _program(db)
    _work_item(db, p, status="blocked")
    db.commit()

    result = get_programs_needing_attention(db, today=today)

    assert len(result) == 1
    assert result[0].id == p.id


def test_get_programs_needing_attention_via_overdue_work_item(db) -> None:
    today = date(2026, 5, 25)
    p = _program(db)
    _work_item(db, p, status="open", due_date=date(2026, 5, 20))
    db.commit()

    result = get_programs_needing_attention(db, today=today)

    assert len(result) == 1
    assert result[0].id == p.id


def test_get_programs_needing_attention_via_stale_dependency(db) -> None:
    today = date(2026, 5, 25)
    now = datetime(2026, 5, 25, 12, 0, tzinfo=timezone.utc)
    p = _program(db)
    dep = _dependency(db, p, status="open")
    dep.last_confirmation_at = now - timedelta(days=15)
    db.commit()

    result = get_programs_needing_attention(db, today=today, now=now)

    assert len(result) == 1
    assert result[0].id == p.id


def test_get_programs_needing_attention_deduplicates(db) -> None:
    today = date(2026, 5, 25)
    p = _program(db)
    _work_item(db, p, status="blocked")
    _work_item(db, p, status="open", due_date=date(2026, 5, 20))
    db.commit()

    result = get_programs_needing_attention(db, today=today)

    assert len(result) == 1


def test_get_programs_needing_attention_excludes_clean_programs(db) -> None:
    today = date(2026, 5, 25)
    p = _program(db)
    _work_item(db, p, status="open", due_date=date(2026, 6, 1))
    db.commit()

    assert get_programs_needing_attention(db, today=today) == []


# ── get_recently_updated_programs ─────────────────────────────────────────────

def test_get_recently_updated_programs_returns_up_to_limit(db) -> None:
    for i in range(12):
        _program(db, name=f"Program {i}")
    db.commit()

    result = get_recently_updated_programs(db, limit=10)

    assert len(result) == 10


def test_get_recently_updated_programs_ordered_by_updated_at(db) -> None:
    now = datetime(2026, 5, 25, 12, 0, tzinfo=timezone.utc)
    p1 = _program(db, name="Old")
    p1.updated_at = now - timedelta(days=5)
    p2 = _program(db, name="Recent")
    p2.updated_at = now - timedelta(days=1)
    db.commit()

    result = get_recently_updated_programs(db, limit=10)

    assert result[0].name == "Recent"
    assert result[1].name == "Old"


# ── operational filtering ─────────────────────────────────────────────────────

def test_blocked_work_item_from_non_operational_program_excluded(db) -> None:
    active_p = _program(db, name="Active Program", status_slug="active")
    _work_item(db, active_p, title="Operational blocked", status="blocked")
    archived_p = _program(db, name="Archived Program", status_slug="archived")
    _work_item(db, archived_p, title="Archived blocked", status="blocked")
    db.commit()

    result = get_blocked_work_items(db)

    titles = {item.title for item in result}
    assert "Operational blocked" in titles
    assert "Archived blocked" not in titles


def test_overdue_work_item_from_non_operational_program_excluded(db) -> None:
    today = date(2026, 5, 25)
    active_p = _program(db, name="Active Program", status_slug="active")
    _work_item(db, active_p, title="Op overdue", status="open", due_date=date(2026, 5, 20))
    completed_p = _program(db, name="Completed Program", status_slug="completed")
    _work_item(db, completed_p, title="Completed overdue", status="open", due_date=date(2026, 5, 20))
    db.commit()

    result = get_overdue_work_items(db, today=today)

    titles = {item.title for item in result}
    assert "Op overdue" in titles
    assert "Completed overdue" not in titles


def test_get_programs_needing_attention_excludes_non_operational(db) -> None:
    today = date(2026, 5, 25)
    active_p = _program(db, name="Active", status_slug="active")
    _work_item(db, active_p, status="blocked")
    paused_p = _program(db, name="Paused", status_slug="paused")
    _work_item(db, paused_p, status="blocked")
    db.commit()

    result = get_programs_needing_attention(db, today=today)

    names = {p.name for p in result}
    assert "Active" in names
    assert "Paused" not in names
