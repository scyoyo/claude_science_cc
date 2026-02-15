from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from enum import Enum


class OnboardingStage(str, Enum):
    """Multi-stage onboarding conversation flow"""
    problem = "problem"
    clarification = "clarification"
    team_suggestion = "team_suggestion"
    mirror_config = "mirror_config"
    complete = "complete"


# --- Chat Request/Response ---

class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str


class OnboardingChatRequest(BaseModel):
    """stage is optional: when omitted, backend infers from context + conversation (semantic flow)."""
    stage: Optional[OnboardingStage] = None
    message: str
    conversation_history: List[ChatMessage] = []
    context: Dict = {}  # Stage-specific context (e.g., analysis results, preferences)
    locale: Optional[str] = None  # System locale fallback for agent language (e.g. "en", "zh")
    """Explicit user intent: e.g. 'accept' when user clicks Agree (no keyword parsing)."""
    intent: Optional[str] = None


class OnboardingChatResponse(BaseModel):
    stage: OnboardingStage
    next_stage: Optional[OnboardingStage] = None
    message: str
    data: Dict = {}  # Structured data (analysis, suggestions, etc.)


# --- Problem Analysis ---

class DomainAnalysis(BaseModel):
    domain: str
    sub_domains: List[str] = []
    key_challenges: List[str] = []
    suggested_approaches: List[str] = []


# --- Agent Suggestion ---

class AgentSuggestion(BaseModel):
    name: str
    title: str
    expertise: str
    goal: str
    role: str
    model: str = "gpt-4.1"
    model_reason: str = ""


class TeamSuggestion(BaseModel):
    team_name: str
    team_description: str
    agents: List[AgentSuggestion]


# --- Mirror Config ---

class MirrorConfig(BaseModel):
    enabled: bool = False
    mirror_model: str = "deepseek-chat"
    agents_to_mirror: List[str] = []  # Agent names to create mirrors for


# --- Generate Team Request ---

class GenerateTeamRequest(BaseModel):
    team_name: str = Field(..., min_length=1, max_length=255)
    team_description: str = ""
    agents: List[AgentSuggestion]
    mirror_config: Optional[MirrorConfig] = None
    language: str = "en"  # Team language preference ("zh", "en")
