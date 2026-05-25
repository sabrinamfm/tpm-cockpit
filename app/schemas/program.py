from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ProgramCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    status: str = "active"  # slug; resolved to status_id in the route handler


class ProgramUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    status: Optional[str] = None  # slug; resolved to status_id in the route handler


class ProgramRead(BaseModel):
    id: int
    name: str
    description: Optional[str]
    status_id: int
    status: str  # slug, sourced from Program.status property
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
