from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Milestone, Program
from app.schemas.milestone import MilestoneCreate, MilestoneRead, MilestoneUpdate

router = APIRouter(tags=["milestones"])


@router.post(
    "/programs/{program_id}/milestones",
    response_model=MilestoneRead,
    status_code=status.HTTP_201_CREATED,
)
def create_milestone(
    program_id: int,
    milestone_in: MilestoneCreate,
    db: Session = Depends(get_db),
) -> Milestone:
    if db.get(Program, program_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")
    milestone = Milestone(program_id=program_id, **milestone_in.model_dump())
    db.add(milestone)
    db.commit()
    db.refresh(milestone)
    return milestone


@router.get("/programs/{program_id}/milestones", response_model=List[MilestoneRead])
def list_milestones(program_id: int, db: Session = Depends(get_db)) -> list[Milestone]:
    if db.get(Program, program_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")
    return list(
        db.scalars(
            select(Milestone)
            .where(Milestone.program_id == program_id)
            .order_by(Milestone.target_date.asc(), Milestone.id.asc())
        )
    )


@router.get("/milestones/{milestone_id}", response_model=MilestoneRead)
def get_milestone(milestone_id: int, db: Session = Depends(get_db)) -> Milestone:
    milestone = db.get(Milestone, milestone_id)
    if milestone is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Milestone not found")
    return milestone


@router.patch("/milestones/{milestone_id}", response_model=MilestoneRead)
def update_milestone(
    milestone_id: int,
    milestone_in: MilestoneUpdate,
    db: Session = Depends(get_db),
) -> Milestone:
    milestone = db.get(Milestone, milestone_id)
    if milestone is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Milestone not found")
    for field, value in milestone_in.model_dump(exclude_unset=True).items():
        setattr(milestone, field, value)
    db.add(milestone)
    db.commit()
    db.refresh(milestone)
    return milestone


@router.delete("/milestones/{milestone_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_milestone(milestone_id: int, db: Session = Depends(get_db)) -> Response:
    milestone = db.get(Milestone, milestone_id)
    if milestone is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Milestone not found")
    db.delete(milestone)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
