from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.models import Agent, Team
from app.schemas.agent import AgentResponse
from app.core.agent_templates import get_all_templates, get_template_by_id, get_templates_by_category
from app.api.agents import generate_system_prompt

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("/")
def list_templates(category: Optional[str] = Query(None)):
    """List available agent templates. Optionally filter by category."""
    if category:
        return get_templates_by_category(category)
    return get_all_templates()


@router.get("/{template_id}")
def get_template(template_id: str):
    """Get a specific agent template."""
    template = get_template_by_id(template_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )
    return template


@router.post("/apply", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
def create_agent_from_template(
    template_id: str = Query(...),
    team_id: str = Query(...),
    db: Session = Depends(get_db),
):
    """Create an agent from a template."""
    template = get_template_by_id(template_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found",
        )

    agent = Agent(
        team_id=team_id,
        name=template["name"],
        title=template["title"],
        expertise=template["expertise"],
        goal=template["goal"],
        role=template["role"],
        model=template["model"],
    )
    agent.system_prompt = generate_system_prompt(agent)

    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent
