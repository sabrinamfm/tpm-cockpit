from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.program import Program
from app.models.program_status import ProgramStatus
from app.schemas.program import ProgramCreate, ProgramRead, ProgramUpdate

router = APIRouter(prefix="/programs", tags=["programs"])


def _resolve_status_slug(db: Session, slug: str) -> ProgramStatus:
    ps = db.scalar(select(ProgramStatus).where(ProgramStatus.slug == slug))
    if ps is None:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid program status: {slug!r}",
        )
    return ps


@router.post("", response_model=ProgramRead, status_code=status.HTTP_201_CREATED)
def create_program(program_in: ProgramCreate, db: Session = Depends(get_db)) -> Program:
    ps = _resolve_status_slug(db, program_in.status)
    program = Program(name=program_in.name, description=program_in.description, status_id=ps.id)
    db.add(program)
    db.commit()
    db.refresh(program)
    return program


@router.get("", response_model=List[ProgramRead])
def list_programs(db: Session = Depends(get_db)) -> list[Program]:
    return list(db.scalars(select(Program).order_by(Program.created_at.desc(), Program.id.desc())))


@router.get("/{program_id}", response_model=ProgramRead)
def get_program(program_id: int, db: Session = Depends(get_db)) -> Program:
    program = db.get(Program, program_id)
    if program is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")
    return program


@router.patch("/{program_id}", response_model=ProgramRead)
def update_program(
    program_id: int,
    program_in: ProgramUpdate,
    db: Session = Depends(get_db),
) -> Program:
    program = db.get(Program, program_id)
    if program is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")

    updates = program_in.model_dump(exclude_unset=True)
    if "status" in updates:
        ps = _resolve_status_slug(db, updates.pop("status"))
        updates["status_id"] = ps.id

    for field, value in updates.items():
        setattr(program, field, value)

    db.add(program)
    db.commit()
    db.refresh(program)
    return program


@router.delete("/{program_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_program(program_id: int, db: Session = Depends(get_db)) -> Response:
    program = db.get(Program, program_id)
    if program is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")

    db.delete(program)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
