from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

MilestoneStatus = Literal["planned", "in_progress", "achieved", "missed", "cancelled"]


class MilestoneBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    target_date: Optional[date] = None
    status: MilestoneStatus = "planned"
    owner: Optional[str] = Field(default=None, max_length=120)


class MilestoneCreate(MilestoneBase):
    pass


class MilestoneUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    target_date: Optional[date] = None
    status: Optional[MilestoneStatus] = None
    owner: Optional[str] = Field(default=None, max_length=120)


class MilestoneRead(MilestoneBase):
    id: int
    display_id: str
    program_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
