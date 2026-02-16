from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import List, Optional


class RoundPlan(BaseModel):
    round: int
    title: str = ""
    goal: str = ""
    expected_output: str = ""


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
    meeting_type: str = "team"  # "team" | "individual" | "merge"
    individual_agent_id: Optional[str] = None
    source_meeting_ids: List[str] = []
    parent_meeting_id: Optional[str] = None
    rewrite_feedback: str = ""
    agenda_strategy: str = "manual"
    max_rounds: int = Field(default=5, ge=1, le=20)
    round_plans: Optional[List[RoundPlan]] = []


class MeetingUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    agenda: Optional[str] = None
    agenda_questions: Optional[List[str]] = None
    agenda_rules: Optional[List[str]] = None
    output_type: Optional[str] = None
    context_meeting_ids: Optional[List[str]] = None
    participant_agent_ids: Optional[List[str]] = None
    meeting_type: Optional[str] = None
    individual_agent_id: Optional[str] = None
    source_meeting_ids: Optional[List[str]] = None
    parent_meeting_id: Optional[str] = None
    rewrite_feedback: Optional[str] = None
    agenda_strategy: Optional[str] = None
    max_rounds: Optional[int] = Field(None, ge=1, le=20)
    round_plans: Optional[List[RoundPlan]] = None


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
    meeting_type: Optional[str] = "team"
    individual_agent_id: Optional[str] = None
    source_meeting_ids: Optional[list] = []
    parent_meeting_id: Optional[str] = None
    rewrite_feedback: Optional[str] = ""
    agenda_strategy: Optional[str] = "manual"
    round_plans: Optional[list] = []
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


class RoundSummary(BaseModel):
    """Summary for a single round."""
    round: int
    summary_text: str = ""
    key_points: List[str] = []


class MeetingSummary(BaseModel):
    """Summary of a meeting. round_summaries = per-round summaries."""

    meeting_id: str
    title: str
    total_rounds: int  # Rounds completed (meeting.current_round)
    max_rounds: int = 5  # Total rounds planned (meeting.max_rounds)
    total_messages: int
    participants: List[str]
    round_summaries: List[RoundSummary] = []  # Per-round summaries (primary)
    key_points: List[str] = []  # Deprecated: use round_summaries
    status: str
    summary_text: Optional[str] = None  # Deprecated: use round_summaries


# ==================== Agenda Strategy Schemas ====================

class AgendaAutoRequest(BaseModel):
    team_id: str
    goal: Optional[str] = ""
    prev_meeting_ids: List[str] = []
    participant_agent_ids: List[str] = []

class AgendaAutoResponse(BaseModel):
    agenda: str
    questions: List[str]
    rules: List[str]
    suggested_rounds: int = 3
    title: str = ""
    round_plans: List[RoundPlan] = []

class AgentVotingRequest(BaseModel):
    team_id: str
    topic: str

class AgentProposal(BaseModel):
    agent_name: str
    proposals: List[str]

class AgentVotingResponse(BaseModel):
    proposals: List[AgentProposal]
    merged_agenda: str

class ChainRecommendRequest(BaseModel):
    prev_meeting_ids: List[str]

class RecommendStrategyRequest(BaseModel):
    team_id: str
    topic: Optional[str] = ""
    has_prev_meetings: bool = False

class RecommendStrategyResponse(BaseModel):
    recommended: str
    reasoning: str


# ==================== Batch Run / Rewrite Schemas ====================

class BatchMeetingRunRequest(BaseModel):
    meeting_id: str
    num_iterations: int = Field(default=3, ge=2, le=10)
    auto_merge: bool = True

class BatchMeetingRunResponse(BaseModel):
    iteration_meeting_ids: List[str]
    merge_meeting_id: Optional[str] = None

class RewriteRequest(BaseModel):
    feedback: str = Field(..., min_length=1)
    rounds: int = Field(default=2, ge=1, le=10)

class ContextPreviewResponse(BaseModel):
    contexts: List[dict]
    total_chars: int
