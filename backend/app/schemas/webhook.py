from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import List, Optional


VALID_EVENTS = [
    "meeting.completed",
    "meeting.failed",
    "artifact.created",
    "team.created",
    "agent.created",
]


class WebhookCreate(BaseModel):
    url: str = Field(..., min_length=1, max_length=2048)
    events: List[str] = Field(..., min_length=1)
    secret: Optional[str] = None


class WebhookUpdate(BaseModel):
    url: Optional[str] = Field(None, min_length=1, max_length=2048)
    events: Optional[List[str]] = None
    is_active: Optional[bool] = None


class WebhookResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    url: str
    events: List[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
