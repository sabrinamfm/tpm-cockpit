from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Decision, Dependency, Milestone, Program, Risk, WorkItem
from app.models.relationship import Relationship
from app.models.status_report import StatusReport
from app.schemas.relationship import RelationshipCreate, RelationshipRead

router = APIRouter(tags=["relationships"])

_OBJECT_MODEL_MAP = {
    "work_item": WorkItem,
    "dependency": Dependency,
    "risk": Risk,
    "status_report": StatusReport,
    "milestone": Milestone,
    "decision": Decision,
}


def _lookup_object(db: Session, object_type: str, object_id: int):
    model = _OBJECT_MODEL_MAP.get(object_type)
    if model is None:
        return None
    return db.get(model, object_id)


@router.post(
    "/relationships",
    response_model=RelationshipRead,
    status_code=status.HTTP_201_CREATED,
)
def create_relationship(
    rel_in: RelationshipCreate,
    db: Session = Depends(get_db),
) -> Relationship:
    if _lookup_object(db, rel_in.source_type, rel_in.source_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{rel_in.source_type} {rel_in.source_id} not found",
        )
    if _lookup_object(db, rel_in.target_type, rel_in.target_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{rel_in.target_type} {rel_in.target_id} not found",
        )
    if rel_in.source_type == rel_in.target_type and rel_in.source_id == rel_in.target_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Source and target cannot be the same object",
        )

    rel = Relationship(**rel_in.model_dump())
    db.add(rel)
    db.commit()
    db.refresh(rel)
    return rel


@router.get("/programs/{program_id}/relationships", response_model=List[RelationshipRead])
def list_program_relationships(
    program_id: int,
    db: Session = Depends(get_db),
) -> list[Relationship]:
    if db.get(Program, program_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")

    wi_ids = list(db.scalars(select(WorkItem.id).where(WorkItem.program_id == program_id)))
    dep_ids = list(db.scalars(select(Dependency.id).where(Dependency.program_id == program_id)))
    risk_ids = list(db.scalars(select(Risk.id).where(Risk.program_id == program_id)))
    sr_ids = list(db.scalars(select(StatusReport.id).where(StatusReport.program_id == program_id)))
    ms_ids = list(db.scalars(select(Milestone.id).where(Milestone.program_id == program_id)))
    dec_ids = list(db.scalars(select(Decision.id).where(Decision.program_id == program_id)))

    conditions = []
    for type_name, ids in [
        ("work_item", wi_ids),
        ("dependency", dep_ids),
        ("risk", risk_ids),
        ("status_report", sr_ids),
        ("milestone", ms_ids),
        ("decision", dec_ids),
    ]:
        if ids:
            conditions.extend([
                (Relationship.source_type == type_name) & (Relationship.source_id.in_(ids)),
                (Relationship.target_type == type_name) & (Relationship.target_id.in_(ids)),
            ])

    if not conditions:
        return []

    return list(
        db.scalars(
            select(Relationship)
            .where(or_(*conditions))
            .order_by(Relationship.created_at.desc())
        )
    )


@router.get("/relationships/{relationship_id}", response_model=RelationshipRead)
def get_relationship(
    relationship_id: int,
    db: Session = Depends(get_db),
) -> Relationship:
    rel = db.get(Relationship, relationship_id)
    if rel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Relationship not found")
    return rel


@router.delete("/relationships/{relationship_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_relationship(
    relationship_id: int,
    db: Session = Depends(get_db),
) -> Response:
    rel = db.get(Relationship, relationship_id)
    if rel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Relationship not found")
    db.delete(rel)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
