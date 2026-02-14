from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional

from app.database import get_db
from app.models import Team, Agent
from app.schemas.team import TeamResponse
from app.schemas.agent import AgentResponse
from app.schemas.pagination import PaginatedResponse
from app.core.auth import get_current_user
from app.models.user import User, UserTeamRole
from app.api.deps import search_pagination_params, build_paginated_response

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/teams", response_model=PaginatedResponse[TeamResponse])
def search_teams(
    q: str = Query(..., min_length=1, max_length=200),
    pagination: tuple[int, int] = Depends(search_pagination_params),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """Search teams by name or description."""
    skip, limit = pagination
    pattern = f"%{q}%"
    query = db.query(Team).filter(
        or_(
            Team.name.ilike(pattern),
            Team.description.ilike(pattern),
        )
    )

    # Filter by access when auth enabled
    if current_user is not None:
        user_team_ids = [
            r.team_id
            for r in db.query(UserTeamRole).filter(UserTeamRole.user_id == current_user.id).all()
        ]
        query = query.filter(
            (Team.owner_id == current_user.id)
            | (Team.id.in_(user_team_ids) if user_team_ids else False)
            | (Team.is_public == True)
        )
    return build_paginated_response(query, skip, limit)


@router.get("/agents", response_model=PaginatedResponse[AgentResponse])
def search_agents(
    q: str = Query(..., min_length=1, max_length=200),
    team_id: Optional[str] = Query(None),
    pagination: tuple[int, int] = Depends(search_pagination_params),
    db: Session = Depends(get_db),
):
    """Search agents by name, title, expertise, or goal. Optionally filter by team."""
    skip, limit = pagination
    pattern = f"%{q}%"
    query = db.query(Agent).filter(
        or_(
            Agent.name.ilike(pattern),
            Agent.title.ilike(pattern),
            Agent.expertise.ilike(pattern),
            Agent.goal.ilike(pattern),
        )
    )
    if team_id:
        query = query.filter(Agent.team_id == team_id)
    return build_paginated_response(query, skip, limit)
