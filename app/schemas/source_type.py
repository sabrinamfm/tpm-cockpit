from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class SourceTypeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class SourceTypeUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    is_active: Optional[bool] = None


class SourceTypeRead(BaseModel):
    id: int
    name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
