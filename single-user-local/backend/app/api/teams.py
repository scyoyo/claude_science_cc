from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.models import Team
from app.models.user import User
from app.schemas.team import TeamCreate, TeamUpdate, TeamResponse, TeamWithAgents
from app.core.auth import get_current_user
from app.core.permissions import check_team_access

router = APIRouter(prefix="/teams", tags=["teams"])


@router.get("/", response_model=List[TeamResponse])
def list_teams(
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """List all teams. When auth enabled, shows user's teams + public teams."""
    if current_user is None:
        # V1 mode or no auth — return all
        return db.query(Team).all()

    from app.models.user import UserTeamRole
    # User's own teams + teams with explicit roles + public teams
    user_team_ids = [
        r.team_id
        for r in db.query(UserTeamRole).filter(UserTeamRole.user_id == current_user.id).all()
    ]
    teams = db.query(Team).filter(
        (Team.owner_id == current_user.id)
        | (Team.id.in_(user_team_ids) if user_team_ids else False)
        | (Team.is_public == True)
    ).all()
    return teams


@router.post("/", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
def create_team(
    team_data: TeamCreate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """Create a new team. Sets current user as owner when auth enabled."""
    data = team_data.model_dump()
    if current_user is not None:
        data["owner_id"] = current_user.id
    team = Team(**data)
    db.add(team)
    db.commit()
    db.refresh(team)
    return team


@router.get("/{team_id}", response_model=TeamWithAgents)
def get_team(
    team_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """Get team details with agents"""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )
    check_team_access(db, current_user, team, min_role="viewer")
    return team


@router.put("/{team_id}", response_model=TeamResponse)
def update_team(
    team_id: str,
    team_data: TeamUpdate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """Update team (requires editor role)"""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )
    check_team_access(db, current_user, team, min_role="editor")

    update_data = team_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(team, field, value)

    db.commit()
    db.refresh(team)
    return team


@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_team(
    team_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """Delete team (requires owner role)"""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )
    check_team_access(db, current_user, team, min_role="owner")

    db.delete(team)
    db.commit()
    return None
