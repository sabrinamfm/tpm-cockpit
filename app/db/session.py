from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings

_DISPLAY_ID_PREFIXES: dict[str, str] = {
    "programs": "PRG",
    "work_items": "WI",
    "dependencies": "DEP",
    "risks": "RSK",
    "status_reports": "SR",
    "relationships": "REL",
    "milestones": "MS",
    "decisions": "DEC",
    "requirements": "REQ",
}


def _register_display_id_events() -> None:
    """Register before_insert mapper events to assign display IDs before the INSERT is emitted."""
    from app.db.base import Base

    @event.listens_for(Base, "before_insert", propagate=True)
    def _assign_display_id(mapper, connection, target):
        prefix = _DISPLAY_ID_PREFIXES.get(getattr(target.__class__, "__tablename__", None))
        if prefix and not target.display_id:
            # MAX(id)+1 matches SQLite's next PK assignment for non-AUTOINCREMENT tables.
            next_id = connection.execute(
                text(f"SELECT COALESCE(MAX(id), 0) + 1 FROM {target.__tablename__}")
            ).scalar()
            target.display_id = f"{prefix}-{next_id:03d}"


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
