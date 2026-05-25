from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ProgramBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    status: str = Field(default="active", min_length=1, max_length=50)


class ProgramCreate(ProgramBase):
    pass


class ProgramUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    status: Optional[str] = Field(default=None, min_length=1, max_length=50)


class ProgramRead(ProgramBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
