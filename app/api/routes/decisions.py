from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Decision, Program
from app.schemas.decision import DecisionCreate, DecisionRead, DecisionUpdate

router = APIRouter(tags=["decisions"])


@router.post(
    "/programs/{program_id}/decisions",
    response_model=DecisionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_decision(
    program_id: int,
    decision_in: DecisionCreate,
    db: Session = Depends(get_db),
) -> Decision:
    if db.get(Program, program_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")
    decision = Decision(program_id=program_id, **decision_in.model_dump())
    db.add(decision)
    db.commit()
    db.refresh(decision)
    return decision


@router.get("/programs/{program_id}/decisions", response_model=List[DecisionRead])
def list_decisions(program_id: int, db: Session = Depends(get_db)) -> list[Decision]:
    if db.get(Program, program_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")
    return list(
        db.scalars(
            select(Decision)
            .where(Decision.program_id == program_id)
            .order_by(Decision.decision_date.asc(), Decision.id.asc())
        )
    )


@router.get("/decisions/{decision_id}", response_model=DecisionRead)
def get_decision(decision_id: int, db: Session = Depends(get_db)) -> Decision:
    decision = db.get(Decision, decision_id)
    if decision is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Decision not found")
    return decision


@router.patch("/decisions/{decision_id}", response_model=DecisionRead)
def update_decision(
    decision_id: int,
    decision_in: DecisionUpdate,
    db: Session = Depends(get_db),
) -> Decision:
    decision = db.get(Decision, decision_id)
    if decision is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Decision not found")
    for field, value in decision_in.model_dump(exclude_unset=True).items():
        setattr(decision, field, value)
    db.add(decision)
    db.commit()
    db.refresh(decision)
    return decision


@router.delete("/decisions/{decision_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_decision(decision_id: int, db: Session = Depends(get_db)) -> Response:
    decision = db.get(Decision, decision_id)
    if decision is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Decision not found")
    db.delete(decision)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
