from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Program, WorkItem
from app.schemas.work_item import WorkItemCreate, WorkItemRead, WorkItemUpdate

router = APIRouter(tags=["work items"])


@router.post(
    "/programs/{program_id}/work-items",
    response_model=WorkItemRead,
    status_code=status.HTTP_201_CREATED,
)
def create_work_item(
    program_id: int,
    work_item_in: WorkItemCreate,
    db: Session = Depends(get_db),
) -> WorkItem:
    program = db.get(Program, program_id)
    if program is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")

    work_item = WorkItem(program_id=program_id, **work_item_in.model_dump())
    db.add(work_item)
    db.commit()
    db.refresh(work_item)
    return work_item


@router.get("/programs/{program_id}/work-items", response_model=List[WorkItemRead])
def list_work_items(program_id: int, db: Session = Depends(get_db)) -> list[WorkItem]:
    program = db.get(Program, program_id)
    if program is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")

    statement = (
        select(WorkItem)
        .where(WorkItem.program_id == program_id)
        .order_by(WorkItem.status.asc(), WorkItem.due_date.asc(), WorkItem.id.asc())
    )
    return list(db.scalars(statement))


@router.get("/work-items/{work_item_id}", response_model=WorkItemRead)
def get_work_item(work_item_id: int, db: Session = Depends(get_db)) -> WorkItem:
    work_item = db.get(WorkItem, work_item_id)
    if work_item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work item not found")
    return work_item


@router.patch("/work-items/{work_item_id}", response_model=WorkItemRead)
def update_work_item(
    work_item_id: int,
    work_item_in: WorkItemUpdate,
    db: Session = Depends(get_db),
) -> WorkItem:
    work_item = db.get(WorkItem, work_item_id)
    if work_item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work item not found")

    for field, value in work_item_in.model_dump(exclude_unset=True).items():
        setattr(work_item, field, value)

    db.add(work_item)
    db.commit()
    db.refresh(work_item)
    return work_item


@router.delete("/work-items/{work_item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_work_item(work_item_id: int, db: Session = Depends(get_db)) -> Response:
    work_item = db.get(WorkItem, work_item_id)
    if work_item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work item not found")

    db.delete(work_item)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
