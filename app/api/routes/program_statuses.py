from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.program import Program
from app.models.program_status import ProgramStatus
from app.schemas.program_status import ProgramStatusCreate, ProgramStatusRead, ProgramStatusUpdate

router = APIRouter(prefix="/program-statuses", tags=["program-statuses"])


@router.get("", response_model=List[ProgramStatusRead])
def list_program_statuses(db: Session = Depends(get_db)) -> list[ProgramStatus]:
    return list(
        db.scalars(
            select(ProgramStatus).order_by(ProgramStatus.sort_order.asc(), ProgramStatus.id.asc())
        )
    )


@router.post("", response_model=ProgramStatusRead, status_code=status.HTTP_201_CREATED)
def create_program_status(
    status_in: ProgramStatusCreate, db: Session = Depends(get_db)
) -> ProgramStatus:
    existing = db.scalar(select(ProgramStatus).where(ProgramStatus.slug == status_in.slug))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slug already exists")
    ps = ProgramStatus(**status_in.model_dump())
    db.add(ps)
    db.commit()
    db.refresh(ps)
    return ps


@router.patch("/{status_id}", response_model=ProgramStatusRead)
def update_program_status(
    status_id: int, status_in: ProgramStatusUpdate, db: Session = Depends(get_db)
) -> ProgramStatus:
    ps = db.get(ProgramStatus, status_id)
    if ps is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program status not found")
    for field, value in status_in.model_dump(exclude_unset=True).items():
        setattr(ps, field, value)
    db.add(ps)
    db.commit()
    db.refresh(ps)
    return ps


@router.delete("/{status_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_program_status(status_id: int, db: Session = Depends(get_db)) -> Response:
    ps = db.get(ProgramStatus, status_id)
    if ps is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program status not found")

    program_count = db.scalar(
        select(func.count()).select_from(Program).where(Program.status_id == status_id)
    )
    if program_count and program_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete a status used by existing programs. Deactivate it instead.",
        )

    db.delete(ps)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
