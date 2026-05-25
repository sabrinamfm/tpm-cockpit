from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Program
from app.schemas.program import ProgramCreate, ProgramRead, ProgramUpdate

router = APIRouter(prefix="/programs", tags=["programs"])


@router.post("", response_model=ProgramRead, status_code=status.HTTP_201_CREATED)
def create_program(program_in: ProgramCreate, db: Session = Depends(get_db)) -> Program:
    program = Program(**program_in.model_dump())
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

    for field, value in program_in.model_dump(exclude_unset=True).items():
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
