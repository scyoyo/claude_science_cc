from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import List, Optional


class MeetingCreate(BaseModel):
    team_id: str
    title: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    agenda: str = ""
    agenda_questions: List[str] = []
    agenda_rules: List[str] = []
    output_type: str = "code"
    context_meeting_ids: List[str] = []
    participant_agent_ids: List[str] = []  # If non-empty, only these agents participate
    max_rounds: int = Field(default=5, ge=1, le=20)


class MeetingUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    agenda: Optional[str] = None
    agenda_questions: Optional[List[str]] = None
    agenda_rules: Optional[List[str]] = None
    output_type: Optional[str] = None
    context_meeting_ids: Optional[List[str]] = None
    participant_agent_ids: Optional[List[str]] = None
    max_rounds: Optional[int] = Field(None, ge=1, le=20)


class MeetingMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    meeting_id: str
    agent_id: Optional[str]
    role: str
    agent_name: Optional[str]
    content: str
    round_number: int
    created_at: datetime


class MeetingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    team_id: str
    title: str
    description: Optional[str] = ""
    agenda: Optional[str] = ""
    agenda_questions: Optional[list] = []
    agenda_rules: Optional[list] = []
    output_type: Optional[str] = "code"
    context_meeting_ids: Optional[list] = []
    participant_agent_ids: Optional[list] = []
    status: str
    max_rounds: int
    current_round: int
    created_at: datetime
    updated_at: datetime


class MeetingWithMessages(MeetingResponse):
    messages: List[MeetingMessageResponse] = []


class MeetingRunRequest(BaseModel):
    """Request to run a meeting round or full meeting."""
    rounds: int = Field(default=1, ge=1, le=20)
    topic: Optional[str] = None  # Optional discussion topic for this run
    locale: Optional[str] = None  # System locale fallback for agent response language ("en", "zh")


class UserMessageRequest(BaseModel):
    """User intervention message during a meeting."""
    content: str = Field(..., min_length=1)


class MeetingSummary(BaseModel):
    meeting_id: str
    title: str
    total_rounds: int
    total_messages: int
    participants: List[str]
    key_points: List[str]
    status: str
