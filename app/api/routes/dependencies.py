from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Dependency, Program
from app.schemas.dependency import DependencyCreate, DependencyRead, DependencyUpdate

router = APIRouter(tags=["dependencies"])


@router.post(
    "/programs/{program_id}/dependencies",
    response_model=DependencyRead,
    status_code=status.HTTP_201_CREATED,
)
def create_dependency(
    program_id: int,
    dependency_in: DependencyCreate,
    db: Session = Depends(get_db),
) -> Dependency:
    program = db.get(Program, program_id)
    if program is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")

    dependency = Dependency(program_id=program_id, **dependency_in.model_dump())
    db.add(dependency)
    db.commit()
    db.refresh(dependency)
    return dependency


@router.get("/programs/{program_id}/dependencies", response_model=List[DependencyRead])
def list_dependencies(program_id: int, db: Session = Depends(get_db)) -> list[Dependency]:
    program = db.get(Program, program_id)
    if program is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")

    statement = (
        select(Dependency)
        .where(Dependency.program_id == program_id)
        .order_by(Dependency.due_date.asc(), Dependency.updated_at.desc(), Dependency.id.asc())
    )
    return list(db.scalars(statement))


@router.get("/dependencies/{dependency_id}", response_model=DependencyRead)
def get_dependency(dependency_id: int, db: Session = Depends(get_db)) -> Dependency:
    dependency = db.get(Dependency, dependency_id)
    if dependency is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dependency not found")
    return dependency


@router.patch("/dependencies/{dependency_id}", response_model=DependencyRead)
def update_dependency(
    dependency_id: int,
    dependency_in: DependencyUpdate,
    db: Session = Depends(get_db),
) -> Dependency:
    dependency = db.get(Dependency, dependency_id)
    if dependency is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dependency not found")

    for field, value in dependency_in.model_dump(exclude_unset=True).items():
        setattr(dependency, field, value)

    db.add(dependency)
    db.commit()
    db.refresh(dependency)
    return dependency


@router.post("/dependencies/{dependency_id}/confirm", response_model=DependencyRead)
def confirm_dependency(dependency_id: int, db: Session = Depends(get_db)) -> Dependency:
    dependency = db.get(Dependency, dependency_id)
    if dependency is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dependency not found")

    dependency.last_confirmation_at = datetime.now(timezone.utc)
    db.add(dependency)
    db.commit()
    db.refresh(dependency)
    return dependency


@router.delete("/dependencies/{dependency_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dependency(dependency_id: int, db: Session = Depends(get_db)) -> Response:
    dependency = db.get(Dependency, dependency_id)
    if dependency is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dependency not found")

    db.delete(dependency)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
