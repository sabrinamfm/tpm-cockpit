from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

MilestoneStatus = Literal["planned", "on_track", "at_risk", "off_track", "blocked", "achieved", "cancelled"]


class MilestoneBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    target_date: Optional[date] = None
    status: MilestoneStatus = "planned"


class MilestoneCreate(MilestoneBase):
    pass


class MilestoneUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    target_date: Optional[date] = None
    status: Optional[MilestoneStatus] = None


class MilestoneRead(MilestoneBase):
    id: int
    display_id: str
    program_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
