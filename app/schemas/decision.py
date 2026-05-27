from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

DecisionStatus = Literal["proposed", "decided", "deferred", "superseded", "cancelled"]


class DecisionBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    decision_date: Optional[date] = None
    status: DecisionStatus = "proposed"
    owner: Optional[str] = Field(default=None, max_length=120)
    rationale: Optional[str] = None


class DecisionCreate(DecisionBase):
    pass


class DecisionUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    decision_date: Optional[date] = None
    status: Optional[DecisionStatus] = None
    owner: Optional[str] = Field(default=None, max_length=120)
    rationale: Optional[str] = None


class DecisionRead(DecisionBase):
    id: int
    display_id: str
    program_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
