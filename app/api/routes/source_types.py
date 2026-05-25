import re
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import SourceType
from app.schemas.source_type import SourceTypeCreate, SourceTypeRead, SourceTypeUpdate

router = APIRouter(prefix="/source-types", tags=["source types"])


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower().strip()).strip("-")


@router.post("", response_model=SourceTypeRead, status_code=status.HTTP_201_CREATED)
def create_source_type(source_type_in: SourceTypeCreate, db: Session = Depends(get_db)) -> SourceType:
    slug = _slugify(source_type_in.slug or source_type_in.name)
    max_order = db.scalar(select(func.max(SourceType.sort_order))) or -1
    source_type = SourceType(name=source_type_in.name.strip(), slug=slug, sort_order=max_order + 1)
    db.add(source_type)
    db.commit()
    db.refresh(source_type)
    return source_type


@router.get("", response_model=List[SourceTypeRead])
def list_source_types(db: Session = Depends(get_db)) -> list[SourceType]:
    return list(
        db.scalars(select(SourceType).order_by(SourceType.sort_order.asc(), SourceType.id.asc()))
    )


@router.patch("/{source_type_id}", response_model=SourceTypeRead)
def update_source_type(
    source_type_id: int,
    source_type_in: SourceTypeUpdate,
    db: Session = Depends(get_db),
) -> SourceType:
    source_type = db.get(SourceType, source_type_id)
    if source_type is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source type not found")

    for field, value in source_type_in.model_dump(exclude_unset=True).items():
        if field == "name" and value is not None:
            value = value.strip()
        setattr(source_type, field, value)

    db.add(source_type)
    db.commit()
    db.refresh(source_type)
    return source_type
