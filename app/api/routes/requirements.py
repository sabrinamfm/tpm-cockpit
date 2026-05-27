from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Program, Requirement
from app.schemas.requirement import RequirementCreate, RequirementRead, RequirementUpdate

router = APIRouter(tags=["requirements"])


@router.post(
    "/programs/{program_id}/requirements",
    response_model=RequirementRead,
    status_code=status.HTTP_201_CREATED,
)
def create_requirement(
    program_id: int,
    requirement_in: RequirementCreate,
    db: Session = Depends(get_db),
) -> Requirement:
    if db.get(Program, program_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")
    requirement = Requirement(program_id=program_id, **requirement_in.model_dump())
    db.add(requirement)
    db.commit()
    db.refresh(requirement)
    return requirement


@router.get("/programs/{program_id}/requirements", response_model=List[RequirementRead])
def list_requirements(program_id: int, db: Session = Depends(get_db)) -> list[Requirement]:
    if db.get(Program, program_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")
    return list(
        db.scalars(
            select(Requirement)
            .where(Requirement.program_id == program_id)
            .order_by(Requirement.target_date.asc(), Requirement.id.asc())
        )
    )


@router.get("/requirements/{requirement_id}", response_model=RequirementRead)
def get_requirement(requirement_id: int, db: Session = Depends(get_db)) -> Requirement:
    requirement = db.get(Requirement, requirement_id)
    if requirement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requirement not found")
    return requirement


@router.patch("/requirements/{requirement_id}", response_model=RequirementRead)
def update_requirement(
    requirement_id: int,
    requirement_in: RequirementUpdate,
    db: Session = Depends(get_db),
) -> Requirement:
    requirement = db.get(Requirement, requirement_id)
    if requirement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requirement not found")
    for field, value in requirement_in.model_dump(exclude_unset=True).items():
        setattr(requirement, field, value)
    db.add(requirement)
    db.commit()
    db.refresh(requirement)
    return requirement


@router.delete("/requirements/{requirement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_requirement(requirement_id: int, db: Session = Depends(get_db)) -> Response:
    requirement = db.get(Requirement, requirement_id)
    if requirement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requirement not found")
    db.delete(requirement)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
