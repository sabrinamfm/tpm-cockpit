from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

ObjectType = Literal["work_item", "dependency", "risk", "status_report", "milestone"]
RelationshipType = Literal[
    "relates_to",
    "blocks",
    "blocked_by",
    "mitigates",
    "tracks",
    "highlights",
    "duplicates",
    "depends_on",
]


class RelationshipCreate(BaseModel):
    source_type: ObjectType
    source_id: int
    relationship_type: RelationshipType
    target_type: ObjectType
    target_id: int
    note: Optional[str] = None


class RelationshipRead(BaseModel):
    id: int
    display_id: str
    source_type: str
    source_id: int
    relationship_type: str
    target_type: str
    target_id: int
    note: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
