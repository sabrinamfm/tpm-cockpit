from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.domain.object_registry import delete_relationships_for_object
from app.models import Feature, Program
from app.schemas.feature import FeatureCreate, FeatureRead, FeatureUpdate

router = APIRouter(tags=["features"])


@router.post(
    "/programs/{program_id}/features",
    response_model=FeatureRead,
    status_code=status.HTTP_201_CREATED,
)
def create_feature(
    program_id: int,
    feature_in: FeatureCreate,
    db: Session = Depends(get_db),
) -> Feature:
    if db.get(Program, program_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")
    feature = Feature(program_id=program_id, **feature_in.model_dump())
    db.add(feature)
    db.commit()
    db.refresh(feature)
    return feature


@router.get("/programs/{program_id}/features", response_model=List[FeatureRead])
def list_features(program_id: int, db: Session = Depends(get_db)) -> list[Feature]:
    if db.get(Program, program_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")
    return list(
        db.scalars(
            select(Feature)
            .where(Feature.program_id == program_id)
            .order_by(Feature.target_date.asc(), Feature.id.asc())
        )
    )


@router.get("/features/{feature_id}", response_model=FeatureRead)
def get_feature(feature_id: int, db: Session = Depends(get_db)) -> Feature:
    feature = db.get(Feature, feature_id)
    if feature is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feature not found")
    return feature


@router.patch("/features/{feature_id}", response_model=FeatureRead)
def update_feature(
    feature_id: int,
    feature_in: FeatureUpdate,
    db: Session = Depends(get_db),
) -> Feature:
    feature = db.get(Feature, feature_id)
    if feature is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feature not found")
    for field, value in feature_in.model_dump(exclude_unset=True).items():
        setattr(feature, field, value)
    db.add(feature)
    db.commit()
    db.refresh(feature)
    return feature


@router.delete("/features/{feature_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_feature(feature_id: int, db: Session = Depends(get_db)) -> Response:
    feature = db.get(Feature, feature_id)
    if feature is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feature not found")
    delete_relationships_for_object(db, "feature", feature_id)
    db.delete(feature)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
