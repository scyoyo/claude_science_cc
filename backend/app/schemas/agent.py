from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Dict, List, Optional


class AgentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    title: str = Field(..., min_length=1, max_length=255)
    expertise: str
    goal: str
    role: str
    model: str = Field(..., min_length=1)
    model_params: Dict = {}
    position_x: float = 0.0
    position_y: float = 0.0


class AgentCreate(AgentBase):
    team_id: str


class AgentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    title: Optional[str] = None
    expertise: Optional[str] = None
    goal: Optional[str] = None
    role: Optional[str] = None
    model: Optional[str] = None
    model_params: Optional[Dict] = None
    position_x: Optional[float] = None
    position_y: Optional[float] = None


class CreateMirrorsRequest(BaseModel):
    primary_agent_ids: List[str] = Field(..., min_length=1, max_length=50)
    mirror_model: str = Field("deepseek-chat", min_length=1)


class AgentResponse(AgentBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    team_id: str
    system_prompt: str
    is_mirror: bool
    primary_agent_id: Optional[str]
    created_at: datetime
    updated_at: datetime
