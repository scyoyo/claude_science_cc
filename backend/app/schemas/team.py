from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import List, Optional


class TeamBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    is_public: bool = False
    language: str = "en"


class TeamCreate(TeamBase):
    pass


class TeamUpdate(TeamBase):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    is_public: Optional[bool] = None
    language: Optional[str] = None


class TeamResponse(TeamBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime


class TeamListResponse(TeamResponse):
    """Team with agent and meeting counts for list views."""

    agent_count: int = 0
    meeting_count: int = 0


class TeamWithAgents(TeamResponse):
    agents: List["AgentResponse"] = []


# Forward reference resolution
from app.schemas.agent import AgentResponse
TeamWithAgents.model_rebuild()
