from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ProgramStatusCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(min_length=1, max_length=50)
    color: str = Field(default="#6b7280", max_length=20)
    sort_order: int = Field(default=0, ge=0)
    is_active: bool = True
    is_default: bool = False


class ProgramStatusUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    color: Optional[str] = Field(default=None, max_length=20)
    sort_order: Optional[int] = Field(default=None, ge=0)
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None


class ProgramStatusRead(BaseModel):
    id: int
    name: str
    slug: str
    color: str
    sort_order: int
    is_active: bool
    is_default: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
