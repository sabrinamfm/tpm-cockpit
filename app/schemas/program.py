from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

ProgramStatus = Literal["active", "paused", "completed", "archived"]


class ProgramBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    status: ProgramStatus = "active"


class ProgramCreate(ProgramBase):
    pass


class ProgramUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    status: Optional[ProgramStatus] = None


class ProgramRead(ProgramBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
