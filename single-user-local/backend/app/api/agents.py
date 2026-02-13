from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import Agent, Team
from app.schemas.agent import AgentCreate, AgentUpdate, AgentResponse
from app.schemas.pagination import PaginatedResponse

router = APIRouter(prefix="/agents", tags=["agents"])


def generate_system_prompt(agent: Agent) -> str:
    """Generate system prompt from agent fields"""
    return (
        f"You are a {agent.title}. "
        f"Your expertise is in {agent.expertise}. "
        f"Your goal is to {agent.goal}. "
        f"Your role is to {agent.role}."
    )


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


@router.get("/team/{team_id}", response_model=PaginatedResponse[AgentResponse])
def list_team_agents(
    team_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """List all agents in a team with pagination"""
    query = db.query(Agent).filter(Agent.team_id == team_id)
    total = query.count()
    items = query.offset(skip).limit(limit).all()
    return PaginatedResponse(items=items, total=total, skip=skip, limit=limit)
