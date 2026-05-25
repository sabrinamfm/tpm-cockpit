from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Program, Risk
from app.schemas.risk import RiskCreate, RiskRead, RiskUpdate

router = APIRouter(tags=["risks"])


@router.post(
    "/programs/{program_id}/risks",
    response_model=RiskRead,
    status_code=status.HTTP_201_CREATED,
)
def create_risk(
    program_id: int,
    risk_in: RiskCreate,
    db: Session = Depends(get_db),
) -> Risk:
    if db.get(Program, program_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")

    risk = Risk(program_id=program_id, **risk_in.model_dump())
    db.add(risk)
    db.commit()
    db.refresh(risk)
    return risk


@router.get("/programs/{program_id}/risks", response_model=List[RiskRead])
def list_risks(program_id: int, db: Session = Depends(get_db)) -> list[Risk]:
    if db.get(Program, program_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")

    return list(
        db.scalars(
            select(Risk)
            .where(Risk.program_id == program_id)
            .order_by(Risk.updated_at.desc(), Risk.id.asc())
        )
    )


@router.get("/risks/{risk_id}", response_model=RiskRead)
def get_risk(risk_id: int, db: Session = Depends(get_db)) -> Risk:
    risk = db.get(Risk, risk_id)
    if risk is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Risk not found")
    return risk


@router.patch("/risks/{risk_id}", response_model=RiskRead)
def update_risk(
    risk_id: int,
    risk_in: RiskUpdate,
    db: Session = Depends(get_db),
) -> Risk:
    risk = db.get(Risk, risk_id)
    if risk is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Risk not found")

    for field, value in risk_in.model_dump(exclude_unset=True).items():
        setattr(risk, field, value)

    db.add(risk)
    db.commit()
    db.refresh(risk)
    return risk


@router.post("/risks/{risk_id}/review", response_model=RiskRead)
def review_risk(risk_id: int, db: Session = Depends(get_db)) -> Risk:
    risk = db.get(Risk, risk_id)
    if risk is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Risk not found")

    risk.last_reviewed_at = datetime.now(timezone.utc)
    db.add(risk)
    db.commit()
    db.refresh(risk)
    return risk


@router.delete("/risks/{risk_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_risk(risk_id: int, db: Session = Depends(get_db)) -> Response:
    risk = db.get(Risk, risk_id)
    if risk is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Risk not found")

    db.delete(risk)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
