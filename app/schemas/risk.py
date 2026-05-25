from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

RiskSeverity = Literal["low", "medium", "high", "critical"]
RiskLikelihood = Literal["unlikely", "possible", "likely", "very_likely"]
RiskStatus = Literal["open", "monitoring", "mitigated", "resolved", "accepted"]


class RiskBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    severity: RiskSeverity = "medium"
    likelihood: RiskLikelihood = "possible"
    status: RiskStatus = "open"
    owner: Optional[str] = Field(default=None, max_length=120)
    mitigation: Optional[str] = None
    target_resolution_date: Optional[date] = None
    last_reviewed_at: Optional[datetime] = None


class RiskCreate(RiskBase):
    pass


class RiskUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    severity: Optional[RiskSeverity] = None
    likelihood: Optional[RiskLikelihood] = None
    status: Optional[RiskStatus] = None
    owner: Optional[str] = Field(default=None, max_length=120)
    mitigation: Optional[str] = None
    target_resolution_date: Optional[date] = None
    last_reviewed_at: Optional[datetime] = None


class RiskRead(RiskBase):
    id: int
    program_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
