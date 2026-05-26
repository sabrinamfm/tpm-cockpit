from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings

_DISPLAY_ID_PREFIXES: dict[str, str] = {
    "programs": "PRG",
    "work_items": "WI",
    "dependencies": "DEP",
    "risks": "RSK",
    "status_reports": "SR",
}


def _register_display_id_events() -> None:
    """Register after_insert mapper events to auto-assign display IDs within the same transaction."""
    from app.db.base import Base

    @event.listens_for(Base, "after_insert", propagate=True)
    def _assign_display_id(mapper, connection, target):
        prefix = _DISPLAY_ID_PREFIXES.get(getattr(target.__class__, "__tablename__", None))
        if prefix and target.id and not target.display_id:
            display_id = f"{prefix}-{target.id:03d}"
            target.display_id = display_id
            connection.execute(
                target.__table__.update()
                .where(target.__table__.c.id == target.id)
                .values(display_id=display_id)
            )


_register_display_id_events()


def _ensure_sqlite_directory(database_url: str) -> None:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        return

    database_path = database_url.removeprefix(prefix)
    if database_path in (":memory:", ""):
        return

    Path(database_path).parent.mkdir(parents=True, exist_ok=True)


settings = get_settings()
_ensure_sqlite_directory(settings.database_url)

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
