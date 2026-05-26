from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

DependencyType = Literal[
    "team",
    "approval",
    "infrastructure",
    "release",
    "vendor",
    "legal",
    "finance",
    "security",
    "product",
    "technical",
    "operational",
]
DependencyStatus = Literal["open", "in_progress", "confirmed", "blocked", "resolved", "cancelled"]
BlockingLevel = Literal["low", "medium", "high", "critical"]


class DependencyBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    dependency_type: DependencyType = "team"
    owner: Optional[str] = Field(default=None, max_length=120)
    external_team: Optional[str] = Field(default=None, max_length=120)
    status: DependencyStatus = "open"
    blocking_level: BlockingLevel = "medium"
    due_date: Optional[date] = None
    last_confirmation_at: Optional[datetime] = None
    notes: Optional[str] = None


class DependencyCreate(DependencyBase):
    pass


class DependencyUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    dependency_type: Optional[DependencyType] = None
    owner: Optional[str] = Field(default=None, max_length=120)
    external_team: Optional[str] = Field(default=None, max_length=120)
    status: Optional[DependencyStatus] = None
    blocking_level: Optional[BlockingLevel] = None
    due_date: Optional[date] = None
    last_confirmation_at: Optional[datetime] = None
    notes: Optional[str] = None


class DependencyRead(DependencyBase):
    id: int
    display_id: Optional[str] = None
    program_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
