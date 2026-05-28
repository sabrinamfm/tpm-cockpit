"""Single source of truth for the object-type → SQLAlchemy model mapping.

All code that needs to look up a model class by its relationship type
string (e.g. "work_item", "milestone") should import from here rather
than maintaining its own copy of this dict.
"""
from typing import Optional

from sqlalchemy import delete as sql_delete, or_
from sqlalchemy.orm import Session

from app.models import Decision, Dependency, Feature, Milestone, Relationship, Requirement, Risk, WorkItem
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


def delete_relationships_for_object(db: Session, object_type: str, object_id: int) -> None:
    """Delete all Relationship rows where the given object appears as source or target.

    Call this inside the same transaction as the object deletion, before db.commit().
    """
    db.execute(
        sql_delete(Relationship).where(
            or_(
                (Relationship.source_type == object_type) & (Relationship.source_id == object_id),
                (Relationship.target_type == object_type) & (Relationship.target_id == object_id),
            )
        )
    )
