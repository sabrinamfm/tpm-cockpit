from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

RequirementSourceType = Literal[
    "okr",
    "change_management",
    "customer_commitment",
    "compliance",
    "leadership_request",
    "strategic_initiative",
    "operational_requirement",
    "other",
]
RequirementStatus = Literal["proposed", "accepted", "in_progress", "delivered", "deferred", "cancelled"]


class RequirementBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    source_type: RequirementSourceType = "other"
    status: RequirementStatus = "proposed"
    owner: Optional[str] = Field(default=None, max_length=120)
    target_date: Optional[date] = None
    link: Optional[str] = Field(default=None, max_length=500)


class RequirementCreate(RequirementBase):
    pass


class RequirementUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    source_type: Optional[RequirementSourceType] = None
    status: Optional[RequirementStatus] = None
    owner: Optional[str] = Field(default=None, max_length=120)
    target_date: Optional[date] = None
    link: Optional[str] = Field(default=None, max_length=500)


class RequirementRead(RequirementBase):
    id: int
    display_id: str
    program_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
