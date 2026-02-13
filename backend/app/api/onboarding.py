from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Team, Agent
from app.api.agents import generate_system_prompt
from app.core.team_builder import TeamBuilder
from app.schemas.onboarding import (
    GenerateTeamRequest,
    OnboardingChatRequest,
    OnboardingChatResponse,
    OnboardingStage,
)
from app.schemas.team import TeamWithAgents

router = APIRouter(prefix="/onboarding", tags=["onboarding"])

# Module-level TeamBuilder instance (no LLM by default)
_team_builder = TeamBuilder()


def get_team_builder() -> TeamBuilder:
    """Dependency for getting TeamBuilder (allows override in tests)."""
    return _team_builder


@router.post("/chat", response_model=OnboardingChatResponse)
def onboarding_chat(
    request: OnboardingChatRequest,
    team_builder: TeamBuilder = Depends(get_team_builder),
):
    """Multi-stage onboarding conversation.

    Stages:
    - problem: User describes research problem → domain analysis
    - clarification: User provides preferences → team suggestion
    - team_suggestion: User reviews team → mirror config prompt
    - mirror_config: User configures mirrors → complete config
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
    """Analyze the user's research problem."""
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
        data=analysis.model_dump(),
    )


def _handle_clarification_stage(
    request: OnboardingChatRequest,
    team_builder: TeamBuilder,
) -> OnboardingChatResponse:
    """Generate team suggestion based on analysis + user preferences."""
    # Reconstruct analysis from context
    analysis_data = request.context.get("analysis")
    if not analysis_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing 'analysis' in context. Complete the 'problem' stage first.",
        )

    from app.schemas.onboarding import DomainAnalysis
    analysis = DomainAnalysis(**analysis_data)

    preferences = request.context.get("preferences", {})
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
        data=suggestion.model_dump(),
    )


def _handle_team_suggestion_stage(
    request: OnboardingChatRequest,
    team_builder: TeamBuilder,
) -> OnboardingChatResponse:
    """Handle user's response to team suggestion."""
    return OnboardingChatResponse(
        stage=OnboardingStage.team_suggestion,
        next_stage=OnboardingStage.mirror_config,
        message=(
            "Would you like to enable mirror agents?\n\n"
            "Mirror agents use a different AI model to independently verify "
            "the primary agents' outputs, helping catch errors and biases.\n\n"
            "If yes, which model should mirrors use? (e.g., claude-3-opus, gpt-4)"
        ),
        data=request.context.get("team_suggestion", {}),
    )


def _handle_mirror_config_stage(
    request: OnboardingChatRequest,
    team_builder: TeamBuilder,
) -> OnboardingChatResponse:
    """Configure mirror agents and produce final config."""
    team_data = request.context.get("team_suggestion", {})
    mirror_config = request.context.get("mirror_config", {})

    data = {
        "team_suggestion": team_data,
        "mirror_config": mirror_config,
    }

    return OnboardingChatResponse(
        stage=OnboardingStage.mirror_config,
        next_stage=OnboardingStage.complete,
        message=(
            "Your team configuration is ready!\n\n"
            "Use the `/api/onboarding/generate-team` endpoint to create "
            "the team and agents in the database."
        ),
        data=data,
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
