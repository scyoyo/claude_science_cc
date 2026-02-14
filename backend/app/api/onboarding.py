import re
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Team, Agent
from app.api.agents import generate_system_prompt
from app.core.team_builder import TeamBuilder
from app.core.llm_client import create_provider
from app.schemas.onboarding import (
    AgentSuggestion,
    ChatMessage,
    DomainAnalysis,
    GenerateTeamRequest,
    OnboardingChatRequest,
    OnboardingChatResponse,
    OnboardingStage,
    TeamSuggestion,
)
from app.schemas.team import TeamWithAgents

router = APIRouter(prefix="/onboarding", tags=["onboarding"])

# Signal words for accept/reject detection
ACCEPT_SIGNALS = [
    "accept", "looks good", "proceed", "yes", "approve", "confirm", "go ahead", "ok", "sure", "great",
    "是", "好", "同意", "可以", "确认", "没问题", "行", "启用", "开启", "enable",
]
REJECT_SIGNALS = [
    "reject", "no", "change", "modify", "different", "revise", "redo", "not good", "disagree",
    "否", "不", "跳过", "不要", "不用", "取消", "skip", "disable",
]


def _create_onboarding_llm_func():
    """Create LLM callable from env var. Falls back to ANTHROPIC_API_KEY if no ONBOARDING_API_KEY."""
    api_key = settings.ONBOARDING_API_KEY or settings.ANTHROPIC_API_KEY
    if not api_key:
        return None
    llm_provider = settings.ONBOARDING_LLM_PROVIDER if settings.ONBOARDING_API_KEY else "anthropic"
    provider = create_provider(llm_provider, api_key)
    model = settings.ONBOARDING_LLM_MODEL

    def llm_func(prompt: str, history: List[ChatMessage]) -> str:
        if history:
            all_messages = [ChatMessage(role="system", content=prompt)] + history
        else:
            # No history: send prompt as user message (Anthropic requires >= 1 non-system message)
            all_messages = [ChatMessage(role="user", content=prompt)]
        response = provider.chat(all_messages, model)
        return response.content

    return llm_func


def get_team_builder() -> TeamBuilder:
    """Dependency: create TeamBuilder per request (picks up latest API key config)."""
    return TeamBuilder(llm_func=_create_onboarding_llm_func())


def _parse_preferences_from_message(message: str) -> dict:
    """Extract team preferences from free-text user message."""
    preferences = {}

    # Extract team size: "3 agents", "team of 5", "5人团队", etc.
    size_match = re.search(r'(\d+)\s*(?:agents?|members?|人|个)', message, re.IGNORECASE)
    if not size_match:
        size_match = re.search(r'team\s+(?:of\s+)?(\d+)', message, re.IGNORECASE)
    if size_match:
        size = int(size_match.group(1))
        if 1 <= size <= 10:
            preferences["team_size"] = size

    # Extract model preference
    model_patterns = [
        r'(gpt-4[o\-a-z]*)',
        r'(gpt-3\.5[a-z\-]*)',
        r'(claude-3[a-z\-]*)',
        r'(claude-sonnet[a-z\-]*)',
        r'(claude-opus[a-z\-]*)',
        r'(deepseek[a-z\-]*)',
    ]
    for pattern in model_patterns:
        model_match = re.search(pattern, message, re.IGNORECASE)
        if model_match:
            preferences["model"] = model_match.group(1).lower()
            break

    return preferences


def _strip_json_block(text: str) -> str:
    """Strip markdown JSON fenced blocks from text so only natural language remains."""
    import re
    stripped = re.sub(r'```(?:json)?\s*\n?.*?\n?```', '', text, flags=re.DOTALL)
    # Collapse multiple blank lines into one
    stripped = re.sub(r'\n{3,}', '\n\n', stripped)
    return stripped.strip()


def _detect_accept_reject(message: str) -> str:
    """Detect whether the user accepts or rejects the team proposal.

    Returns 'accept', 'reject', or 'unclear'.
    """
    msg_lower = message.lower()
    accept_score = sum(1 for s in ACCEPT_SIGNALS if s in msg_lower)
    reject_score = sum(1 for s in REJECT_SIGNALS if s in msg_lower)
    if reject_score > accept_score:
        return "reject"
    if accept_score > 0:
        return "accept"
    return "unclear"


@router.post("/chat", response_model=OnboardingChatResponse)
def onboarding_chat(
    request: OnboardingChatRequest,
    team_builder: TeamBuilder = Depends(get_team_builder),
):
    """Multi-stage onboarding conversation.

    Stages:
    - problem: User describes research problem → LLM asks clarifying questions
    - clarification: User answers questions → LLM proposes team as JSON
    - team_suggestion: User accepts/rejects → accept goes to mirrors, reject re-proposes
    - mirror_config: LLM explains mirrors → final config
    - complete: Final summary
    """
    if request.stage == OnboardingStage.problem:
        return _handle_problem_stage(request, team_builder)
    elif request.stage == OnboardingStage.clarification:
        return _handle_clarification_stage(request, team_builder)
    elif request.stage == OnboardingStage.team_suggestion:
        return _handle_team_suggestion_stage(request, team_builder)
    elif request.stage == OnboardingStage.mirror_config:
        return _handle_mirror_config_stage(request, team_builder)
    elif request.stage == OnboardingStage.complete:
        return _handle_complete_stage(request)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown stage: {request.stage}",
        )


def _handle_problem_stage(
    request: OnboardingChatRequest,
    team_builder: TeamBuilder,
) -> OnboardingChatResponse:
    """Analyze the user's research problem.

    LLM mode: Ask 2-3 clarifying questions as natural text.
    Template mode: Return domain analysis with structured prompts.
    """
    if team_builder.llm_func:
        # LLM mode: generate clarifying response
        response_text = team_builder.generate_clarifying_response(
            request.message, request.conversation_history
        )
        return OnboardingChatResponse(
            stage=OnboardingStage.problem,
            next_stage=OnboardingStage.clarification,
            message=response_text,
            data={},
        )

    # Template mode: keyword-based analysis
    analysis = team_builder.analyze_problem(request.message)
    return OnboardingChatResponse(
        stage=OnboardingStage.problem,
        next_stage=OnboardingStage.clarification,
        message=(
            f"I've identified your research domain as **{analysis.domain}**, "
            f"covering {', '.join(analysis.sub_domains)}.\n\n"
            f"Key challenges: {', '.join(analysis.key_challenges)}.\n\n"
            "Please share any preferences for your team:\n"
            "- Preferred team size (2-5 agents)?\n"
            "- Any specific model preference (e.g., gpt-4, claude-3-opus)?\n"
            "- Any particular focus area?"
        ),
        data={"analysis": analysis.model_dump()},
    )


def _handle_clarification_stage(
    request: OnboardingChatRequest,
    team_builder: TeamBuilder,
) -> OnboardingChatResponse:
    """Generate team suggestion based on conversation.

    LLM mode: LLM proposes full team as JSON based on conversation history.
    Template mode: Parse preferences + use template team composition.
    """
    if team_builder.llm_func:
        # LLM mode: propose team from full conversation history
        history = list(request.conversation_history)
        if request.message:
            history.append(ChatMessage(role="user", content=request.message))

        suggestion, raw_text = team_builder.propose_team_with_text(history)
        if suggestion:
            # Strip JSON block from LLM text - team cards are rendered by frontend
            display_text = _strip_json_block(raw_text) if raw_text else (
                f"Here's your suggested team: **{suggestion.team_name}**"
            )
            return OnboardingChatResponse(
                stage=OnboardingStage.clarification,
                next_stage=OnboardingStage.team_suggestion,
                message=display_text,
                data={
                    "team_suggestion": suggestion.model_dump(),
                    "proposed_team": [a.model_dump() for a in suggestion.agents],
                },
            )
        # LLM failed to produce valid JSON — ask user for more detail instead of crashing
        return OnboardingChatResponse(
            stage=OnboardingStage.clarification,
            next_stage=OnboardingStage.clarification,
            message=(
                raw_text if raw_text else
                "Could you tell me more about your research goals? "
                "For example, what specific problem are you trying to solve, "
                "and what kind of expertise would be most helpful?"
            ),
            data={},
        )

    # Template mode: reconstruct analysis from context (or generate it on the fly)
    analysis_data = request.context.get("analysis")
    if not analysis_data:
        # Auto-generate analysis from the user's message
        analysis = team_builder.analyze_problem(request.message)
        analysis_data = analysis.model_dump()

    analysis = DomainAnalysis(**analysis_data)
    parsed = _parse_preferences_from_message(request.message)
    preferences = {**parsed, **request.context.get("preferences", {})}
    suggestion = team_builder.suggest_team_composition(analysis, preferences)

    agent_summary = "\n".join(
        f"- **{a.name}** ({a.title}): {a.expertise}"
        for a in suggestion.agents
    )

    return OnboardingChatResponse(
        stage=OnboardingStage.clarification,
        next_stage=OnboardingStage.team_suggestion,
        message=(
            f"Here's your suggested team: **{suggestion.team_name}**\n\n"
            f"{agent_summary}\n\n"
            "Would you like to:\n"
            "1. Accept this team configuration\n"
            "2. Modify the team (add/remove/edit agents)\n"
            "3. Enable mirror agents for cross-validation"
        ),
        data={"team_suggestion": suggestion.model_dump()},
    )


def _handle_team_suggestion_stage(
    request: OnboardingChatRequest,
    team_builder: TeamBuilder,
) -> OnboardingChatResponse:
    """Handle user's response to team suggestion.

    Detect accept/reject:
    - Accept → move to mirror_config (LLM explains mirrors or static message)
    - Reject → re-propose team with feedback (loop back to clarification stage)
    """
    decision = _detect_accept_reject(request.message)

    if decision == "reject":
        # Re-propose team with user feedback
        if team_builder.llm_func:
            history = list(request.conversation_history)
            if request.message:
                history.append(ChatMessage(role="user", content=request.message))
            suggestion, raw_text = team_builder.propose_team_with_text(history)
            if suggestion:
                display_text = _strip_json_block(raw_text) if raw_text else (
                    f"Here's a revised team: **{suggestion.team_name}**"
                )
                return OnboardingChatResponse(
                    stage=OnboardingStage.team_suggestion,
                    next_stage=OnboardingStage.team_suggestion,
                    message=display_text,
                    data={
                        "team_suggestion": suggestion.model_dump(),
                        "proposed_team": [a.model_dump() for a in suggestion.agents],
                    },
                )
        # Template fallback: re-ask
        return OnboardingChatResponse(
            stage=OnboardingStage.team_suggestion,
            next_stage=OnboardingStage.team_suggestion,
            message=(
                "I understand you'd like changes. Please describe what you'd like to modify "
                "(e.g., different agents, different size, different models)."
            ),
            data={"team_suggestion": request.context.get("team_suggestion", {})},
        )

    # Accept (or unclear → default to accept and proceed)
    if team_builder.llm_func:
        history = list(request.conversation_history)
        mirror_explanation = team_builder.explain_mirrors(history)
        return OnboardingChatResponse(
            stage=OnboardingStage.team_suggestion,
            next_stage=OnboardingStage.mirror_config,
            message=mirror_explanation,
            data={"team_suggestion": request.context.get("team_suggestion", {})},
        )

    return OnboardingChatResponse(
        stage=OnboardingStage.team_suggestion,
        next_stage=OnboardingStage.mirror_config,
        message=(
            "Would you like to enable mirror agents?\n\n"
            "Mirror agents use a different AI model to independently verify "
            "the primary agents' outputs, helping catch errors and biases.\n\n"
            "If yes, which model should mirrors use? (e.g., claude-3-opus, gpt-4)"
        ),
        data={"team_suggestion": request.context.get("team_suggestion", {})},
    )


def _handle_mirror_config_stage(
    request: OnboardingChatRequest,
    team_builder: TeamBuilder,
) -> OnboardingChatResponse:
    """Configure mirror agents based on user's response."""
    team_data = request.context.get("team_suggestion", {})

    # Parse user's response for yes/no
    decision = _detect_accept_reject(request.message)
    enable_mirrors = decision == "accept"

    # Extract model preference from user's message (default: deepseek-chat)
    mirror_model = "deepseek-chat"
    parsed = _parse_preferences_from_message(request.message)
    if parsed.get("model"):
        mirror_model = parsed["model"]

    mirror_config = {
        "enabled": enable_mirrors,
        "mirror_model": mirror_model,
        "agents_to_mirror": [],  # Mirror all agents
    }

    if enable_mirrors:
        msg = f"Mirror agents enabled using **{mirror_model}**. Creating your team now..."
    else:
        msg = "Mirror agents skipped. Creating your team now..."

    return OnboardingChatResponse(
        stage=OnboardingStage.mirror_config,
        next_stage=None,
        message=msg,
        data={
            "team_suggestion": team_data,
            "mirror_config": mirror_config,
        },
    )


def _handle_complete_stage(
    request: OnboardingChatRequest,
) -> OnboardingChatResponse:
    """Final stage - summary."""
    return OnboardingChatResponse(
        stage=OnboardingStage.complete,
        next_stage=None,
        message="Onboarding complete! Your team has been configured.",
        data={},
    )


@router.post("/generate-team", response_model=TeamWithAgents, status_code=status.HTTP_201_CREATED)
def generate_team(
    request: GenerateTeamRequest,
    db: Session = Depends(get_db),
    team_builder: TeamBuilder = Depends(get_team_builder),
):
    """Create a team and its agents from the onboarding configuration."""
    # Create team
    team = Team(name=request.team_name, description=request.team_description)
    db.add(team)
    db.commit()
    db.refresh(team)

    # Create primary agents
    created_agents = []
    agent_name_to_id = {}
    for agent_data in request.agents:
        agent = Agent(
            team_id=str(team.id),
            name=agent_data.name,
            title=agent_data.title,
            expertise=agent_data.expertise,
            goal=agent_data.goal,
            role=agent_data.role,
            model=agent_data.model,
            system_prompt="",  # Placeholder, will be set below
        )
        agent.system_prompt = generate_system_prompt(agent)
        db.add(agent)
        db.commit()
        db.refresh(agent)
        created_agents.append(agent)
        agent_name_to_id[agent_data.name] = str(agent.id)

    # Create mirror agents if configured
    if request.mirror_config and request.mirror_config.enabled:
        agents_to_mirror = request.mirror_config.agents_to_mirror
        mirror_model = request.mirror_config.mirror_model

        for agent_data in request.agents:
            if agents_to_mirror and agent_data.name not in agents_to_mirror:
                continue

            primary_id = agent_name_to_id[agent_data.name]
            mirror_suggestions = team_builder.create_mirror_agents(
                [agent_data], mirror_model
            )
            for mirror_data in mirror_suggestions:
                mirror = Agent(
                    team_id=str(team.id),
                    name=mirror_data.name,
                    title=mirror_data.title,
                    expertise=mirror_data.expertise,
                    goal=mirror_data.goal,
                    role=mirror_data.role,
                    model=mirror_data.model,
                    system_prompt="",
                    is_mirror=True,
                    primary_agent_id=primary_id,
                )
                mirror.system_prompt = generate_system_prompt(mirror)
                db.add(mirror)
                db.commit()
                db.refresh(mirror)
                created_agents.append(mirror)

    # Refresh team to include all agents
    db.refresh(team)
    return team
