from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional

from sqlalchemy import func
from app.database import get_db
from app.models import Agent, Team, MeetingMessage
from app.schemas.agent import AgentCreate, AgentUpdate, AgentResponse
from app.schemas.pagination import PaginatedResponse
from app.core.prompt import generate_system_prompt
from app.api.deps import pagination_params, build_paginated_response

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("/", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
def create_agent(agent_data: AgentCreate, db: Session = Depends(get_db)):
    """Create a new agent"""
    # Verify team exists
    team = db.query(Team).filter(Team.id == agent_data.team_id).first()
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )

    # Create agent
    agent = Agent(**agent_data.model_dump())
    agent.system_prompt = generate_system_prompt(agent)

    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


@router.post("/batch", response_model=List[AgentResponse], status_code=status.HTTP_201_CREATED)
def batch_create_agents(
    agents_data: List[AgentCreate],
    db: Session = Depends(get_db),
):
    """Create multiple agents at once. All must belong to valid teams."""
    if not agents_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty agent list",
        )
    if len(agents_data) > 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 50 agents per batch",
        )

    # Validate all team IDs upfront
    team_ids = {a.team_id for a in agents_data}
    existing_teams = {
        t.id for t in db.query(Team).filter(Team.id.in_(team_ids)).all()
    }
    missing = team_ids - existing_teams
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Teams not found: {', '.join(missing)}",
        )

    created = []
    for agent_data in agents_data:
        agent = Agent(**agent_data.model_dump())
        agent.system_prompt = generate_system_prompt(agent)
        db.add(agent)
        created.append(agent)

    db.commit()
    for a in created:
        db.refresh(a)
    return created


@router.delete("/batch", status_code=status.HTTP_200_OK)
def batch_delete_agents(
    agent_ids: List[str],
    db: Session = Depends(get_db),
):
    """Delete multiple agents by IDs. Returns count of deleted agents."""
    if not agent_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty ID list",
        )
    deleted = db.query(Agent).filter(Agent.id.in_(agent_ids)).delete(synchronize_session="fetch")
    db.commit()
    return {"deleted": deleted}


@router.get("/team/{team_id}", response_model=PaginatedResponse[AgentResponse])
def list_team_agents(
    team_id: str,
    pagination: tuple[int, int] = Depends(pagination_params),
    db: Session = Depends(get_db),
):
    """List all agents in a team with pagination"""
    skip, limit = pagination
    query = db.query(Agent).filter(Agent.team_id == team_id)
    return build_paginated_response(query, skip, limit)


@router.get("/{agent_id}", response_model=AgentResponse)
def get_agent(agent_id: str, db: Session = Depends(get_db)):
    """Get agent details"""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )
    return agent


@router.get("/{agent_id}/metrics")
def get_agent_metrics(agent_id: str, db: Session = Depends(get_db)):
    """Get agent performance metrics from meeting participation."""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    messages = db.query(MeetingMessage).filter(MeetingMessage.agent_id == agent_id).all()

    total_messages = len(messages)
    meeting_ids = list({m.meeting_id for m in messages})
    total_meetings = len(meeting_ids)

    avg_length = 0
    if total_messages > 0:
        avg_length = round(sum(len(m.content) for m in messages) / total_messages)

    # Most active round
    round_counts = {}
    for m in messages:
        round_counts[m.round_number] = round_counts.get(m.round_number, 0) + 1
    most_active_round = max(round_counts, key=round_counts.get) if round_counts else None

    return {
        "agent_id": agent_id,
        "agent_name": agent.name,
        "total_meetings": total_meetings,
        "total_messages": total_messages,
        "avg_message_length": avg_length,
        "most_active_round": most_active_round,
    }


@router.post("/{agent_id}/clone", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
def clone_agent(
    agent_id: str,
    team_id: Optional[str] = Query(None, description="Target team ID (defaults to same team)"),
    db: Session = Depends(get_db),
):
    """Clone an agent's configuration. Optionally move to a different team."""
    original = db.query(Agent).filter(Agent.id == agent_id).first()
    if not original:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    target_team_id = team_id or original.team_id
    if team_id:
        team = db.query(Team).filter(Team.id == team_id).first()
        if not team:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target team not found")

    clone = Agent(
        team_id=target_team_id,
        name=f"{original.name} (copy)",
        title=original.title,
        expertise=original.expertise,
        goal=original.goal,
        role=original.role,
        model=original.model,
        model_params=original.model_params or {},
        position_x=original.position_x + 50,
        position_y=original.position_y + 50,
    )
    clone.system_prompt = generate_system_prompt(clone)
    db.add(clone)
    db.commit()
    db.refresh(clone)
    return clone


@router.put("/{agent_id}", response_model=AgentResponse)
def update_agent(
    agent_id: str,
    agent_data: AgentUpdate,
    db: Session = Depends(get_db)
):
    """Update agent"""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )

    # Update fields
    update_data = agent_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(agent, field, value)

    # Regenerate system prompt if relevant fields changed
    if any(field in update_data for field in ['title', 'expertise', 'goal', 'role']):
        agent.system_prompt = generate_system_prompt(agent)

    db.commit()
    db.refresh(agent)
    return agent


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_agent(agent_id: str, db: Session = Depends(get_db)):
    """Delete agent"""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )

    db.delete(agent)
    db.commit()
    return None
