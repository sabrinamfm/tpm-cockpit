from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class SourceTypeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slug: Optional[str] = Field(default=None, max_length=50)


class SourceTypeUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    is_active: Optional[bool] = None


class SourceTypeRead(BaseModel):
    id: int
    name: str
    slug: str
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
