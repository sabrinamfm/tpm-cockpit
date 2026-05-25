from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

WorkItemStatus = Literal["open", "in_progress", "blocked", "completed", "cancelled"]


class WorkItemBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    status: WorkItemStatus = "open"
    owner: Optional[str] = Field(default=None, max_length=120)
    source_type_id: Optional[int] = None
    link: Optional[str] = Field(default=None, max_length=500)
    due_date: Optional[date] = None


class WorkItemCreate(WorkItemBase):
    pass


class WorkItemUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    status: Optional[WorkItemStatus] = None
    owner: Optional[str] = Field(default=None, max_length=120)
    source_type_id: Optional[int] = None
    link: Optional[str] = Field(default=None, max_length=500)
    due_date: Optional[date] = None


class WorkItemRead(WorkItemBase):
    id: int
    program_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
