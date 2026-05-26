from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

ReportedHealth = Literal["on_track", "at_risk", "off_track"]


class StatusReportCreate(BaseModel):
    report_date: date
    reported_health: ReportedHealth
    health_rationale: Optional[str] = None
    summary: Optional[str] = None


class StatusReportUpdate(BaseModel):
    report_date: Optional[date] = None
    reported_health: Optional[ReportedHealth] = None
    health_rationale: Optional[str] = None
    summary: Optional[str] = None


class StatusReportRead(BaseModel):
    id: int
    display_id: str
    program_id: int
    report_date: date
    reported_health: str
    suggested_health: str
    health_rationale: Optional[str]
    summary: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
