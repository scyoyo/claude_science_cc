"""RBAC permission checks for team-level authorization.

When AUTH_ENABLED=False (V1 mode), all checks pass (user is None).
When AUTH_ENABLED=True, checks team ownership and UserTeamRole.
"""

from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.team import Team
from app.models.user import User, UserTeamRole


def get_team_role(db: Session, user: Optional[User], team: Team) -> Optional[str]:
    """Get user's role for a team. Returns 'owner', 'editor', 'viewer', or None."""
    if user is None:
        return None  # V1 mode — no auth

    # Team owner always has full access
    if team.owner_id == user.id:
        return "owner"

    # Admin has full access
    if user.is_admin:
        return "owner"

    # Check explicit role assignment
    role_record = db.query(UserTeamRole).filter(
        UserTeamRole.user_id == user.id,
        UserTeamRole.team_id == team.id,
    ).first()

    if role_record:
        return role_record.role

    # Public teams are viewable by anyone
    if team.is_public:
        return "viewer"

    return None


def check_team_access(
    db: Session,
    user: Optional[User],
    team: Team,
    min_role: str = "viewer",
) -> None:
    """Check that user has at least min_role access to team.

    Raises 403 if insufficient permissions, 404 if no access at all.
    When user is None (V1 mode), always passes.
    """
    if user is None:
        return  # V1 mode — no restrictions

    role = get_team_role(db, user, team)

    if role is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found",
        )

    role_hierarchy = {"viewer": 0, "editor": 1, "owner": 2}
    if role_hierarchy.get(role, -1) < role_hierarchy.get(min_role, 0):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires {min_role} role or higher",
        )
