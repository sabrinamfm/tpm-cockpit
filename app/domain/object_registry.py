"""Single source of truth for the object-type → SQLAlchemy model mapping.

All code that needs to look up a model class by its relationship type
string (e.g. "work_item", "milestone") should import from here rather
than maintaining its own copy of this dict.
"""
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Decision, Dependency, Feature, Milestone, Requirement, Risk, WorkItem
from app.models.status_report import StatusReport

OBJECT_REGISTRY: dict[str, type] = {
    "work_item": WorkItem,
    "dependency": Dependency,
    "risk": Risk,
    "status_report": StatusReport,
    "milestone": Milestone,
    "decision": Decision,
    "requirement": Requirement,
    "feature": Feature,
}

VALID_OBJECT_TYPES: frozenset[str] = frozenset(OBJECT_REGISTRY.keys())


def lookup_object(db: Session, object_type: str, object_id: int) -> Optional[object]:
    """Return the ORM instance for (object_type, object_id), or None."""
    model = OBJECT_REGISTRY.get(object_type)
    if model is None:
        return None
    return db.get(model, object_id)
