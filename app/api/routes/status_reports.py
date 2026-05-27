from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.domain.health import compute_suggested_health
from app.models import Program, StatusReport
from app.models.dependency import Dependency
from app.models.risk import Risk
from app.models.work_item import WorkItem
from app.schemas.status_report import StatusReportCreate, StatusReportRead, StatusReportUpdate

router = APIRouter(tags=["status_reports"])


def _load_program_with_relations(db: Session, program_id: int) -> Program | None:
    return db.scalars(
        select(Program)
        .options(
            selectinload(Program.work_items),
            selectinload(Program.dependencies),
            selectinload(Program.risks),
        )
        .where(Program.id == program_id)
    ).one_or_none()


@router.post(
    "/programs/{program_id}/status-reports",
    response_model=StatusReportRead,
    status_code=status.HTTP_201_CREATED,
)
def create_status_report(
    program_id: int,
    report_in: StatusReportCreate,
    db: Session = Depends(get_db),
) -> StatusReport:
    program = _load_program_with_relations(db, program_id)
    if program is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")

    week = report_in.report_date.isocalendar().week
    report = StatusReport(
        program_id=program_id,
        report_title=f"Week {week} {program.name} Report",
        suggested_health=compute_suggested_health(program),
        **report_in.model_dump(),
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


@router.get("/programs/{program_id}/status-reports", response_model=List[StatusReportRead])
def list_status_reports(program_id: int, db: Session = Depends(get_db)) -> list[StatusReport]:
    if db.get(Program, program_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")

    return list(
        db.scalars(
            select(StatusReport)
            .where(StatusReport.program_id == program_id)
            .order_by(StatusReport.report_date.desc(), StatusReport.created_at.desc())
        )
    )


@router.get("/status-reports/{report_id}", response_model=StatusReportRead)
def get_status_report(report_id: int, db: Session = Depends(get_db)) -> StatusReport:
    report = db.get(StatusReport, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Status report not found")
    return report


@router.patch("/status-reports/{report_id}", response_model=StatusReportRead)
def update_status_report(
    report_id: int,
    report_in: StatusReportUpdate,
    db: Session = Depends(get_db),
) -> StatusReport:
    report = db.get(StatusReport, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Status report not found")

    for field, value in report_in.model_dump(exclude_unset=True).items():
        setattr(report, field, value)

    db.add(report)
    db.commit()
    db.refresh(report)
    return report


@router.delete("/status-reports/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_status_report(report_id: int, db: Session = Depends(get_db)) -> Response:
    report = db.get(StatusReport, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Status report not found")

    db.delete(report)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
