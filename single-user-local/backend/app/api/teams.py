from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.models import Team, Agent, Meeting, MeetingMessage, CodeArtifact
from app.models.user import User, UserTeamRole
from app.schemas.team import TeamCreate, TeamUpdate, TeamResponse, TeamWithAgents
from app.schemas.user import TeamRoleAssign, TeamRoleResponse
from app.schemas.pagination import PaginatedResponse
from app.core.auth import get_current_user
from app.core.permissions import check_team_access

router = APIRouter(prefix="/teams", tags=["teams"])


@router.get("/", response_model=PaginatedResponse[TeamResponse])
def list_teams(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """List teams with pagination. When auth enabled, shows user's teams + public teams."""
    if current_user is None:
        query = db.query(Team)
    else:
        user_team_ids = [
            r.team_id
            for r in db.query(UserTeamRole).filter(UserTeamRole.user_id == current_user.id).all()
        ]
        query = db.query(Team).filter(
            (Team.owner_id == current_user.id)
            | (Team.id.in_(user_team_ids) if user_team_ids else False)
            | (Team.is_public == True)
        )

    total = query.count()
    items = query.offset(skip).limit(limit).all()
    return PaginatedResponse(items=items, total=total, skip=skip, limit=limit)


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


@router.get("/{team_id}/stats")
def get_team_stats(
    team_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """Get team statistics: counts of agents, meetings, messages, artifacts."""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    check_team_access(db, current_user, team, min_role="viewer")

    agent_count = db.query(Agent).filter(Agent.team_id == team_id).count()
    meeting_count = db.query(Meeting).filter(Meeting.team_id == team_id).count()
    completed_meetings = db.query(Meeting).filter(
        Meeting.team_id == team_id, Meeting.status == "completed"
    ).count()

    # Get message count across all team meetings
    meeting_ids = [m.id for m in db.query(Meeting.id).filter(Meeting.team_id == team_id).all()]
    message_count = 0
    artifact_count = 0
    if meeting_ids:
        message_count = db.query(MeetingMessage).filter(
            MeetingMessage.meeting_id.in_(meeting_ids)
        ).count()
        artifact_count = db.query(CodeArtifact).filter(
            CodeArtifact.meeting_id.in_(meeting_ids)
        ).count()

    return {
        "team_id": team_id,
        "agent_count": agent_count,
        "meeting_count": meeting_count,
        "completed_meetings": completed_meetings,
        "message_count": message_count,
        "artifact_count": artifact_count,
    }


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


# ==================== Team Sharing ====================


@router.get("/{team_id}/members", response_model=List[TeamRoleResponse])
def list_team_members(
    team_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """List team members and their roles (requires viewer access)."""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    check_team_access(db, current_user, team, min_role="viewer")
    return db.query(UserTeamRole).filter(UserTeamRole.team_id == team_id).all()


@router.post("/{team_id}/members", response_model=TeamRoleResponse, status_code=status.HTTP_201_CREATED)
def add_team_member(
    team_id: str,
    data: TeamRoleAssign,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """Add a member to the team (requires owner role)."""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    check_team_access(db, current_user, team, min_role="owner")

    # Verify target user exists
    target = db.query(User).filter(User.id == data.user_id).first()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Check if already a member
    existing = db.query(UserTeamRole).filter(
        UserTeamRole.user_id == data.user_id,
        UserTeamRole.team_id == team_id,
    ).first()
    if existing:
        existing.role = data.role
        db.commit()
        db.refresh(existing)
        return existing

    role = UserTeamRole(user_id=data.user_id, team_id=team_id, role=data.role)
    db.add(role)
    db.commit()
    db.refresh(role)
    return role


@router.delete("/{team_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_team_member(
    team_id: str,
    user_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """Remove a member from the team (requires owner role)."""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    check_team_access(db, current_user, team, min_role="owner")

    role = db.query(UserTeamRole).filter(
        UserTeamRole.user_id == user_id,
        UserTeamRole.team_id == team_id,
    ).first()
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    db.delete(role)
    db.commit()
    return None
