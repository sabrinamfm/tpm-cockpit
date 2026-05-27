from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

FeatureStatus = Literal["proposed", "planned", "in_progress", "blocked", "delivered", "deferred", "cancelled"]


class FeatureBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    status: FeatureStatus = "proposed"
    owner: Optional[str] = Field(default=None, max_length=120)
    target_date: Optional[date] = None
    link: Optional[str] = Field(default=None, max_length=500)


class FeatureCreate(FeatureBase):
    pass


class FeatureUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    status: Optional[FeatureStatus] = None
    owner: Optional[str] = Field(default=None, max_length=120)
    target_date: Optional[date] = None
    link: Optional[str] = Field(default=None, max_length=500)


class FeatureRead(FeatureBase):
    id: int
    display_id: str
    program_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
