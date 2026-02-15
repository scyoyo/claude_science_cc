from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import Team, Agent, Meeting, MeetingMessage, CodeArtifact

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    """Aggregated dashboard statistics."""
    total_teams = db.query(func.count(Team.id)).scalar()
    total_agents = db.query(func.count(Agent.id)).scalar()
    total_meetings = db.query(func.count(Meeting.id)).scalar()
    completed_meetings = db.query(func.count(Meeting.id)).filter(
        Meeting.status == "completed"
    ).scalar()
    total_artifacts = db.query(func.count(CodeArtifact.id)).scalar()
    total_messages = db.query(func.count(MeetingMessage.id)).scalar()

    # Recent meetings (last 5 by updated_at)
    recent = (
        db.query(Meeting, Team.name.label("team_name"))
        .join(Team, Meeting.team_id == Team.id)
        .order_by(Meeting.updated_at.desc())
        .limit(5)
        .all()
    )
    recent_meetings = [
        {
            "id": m.id,
            "title": m.title,
            "team_id": m.team_id,
            "team_name": team_name,
            "status": m.status,
            "current_round": m.current_round,
            "max_rounds": m.max_rounds,
            "updated_at": m.updated_at.isoformat() if m.updated_at else None,
        }
        for m, team_name in recent
    ]

    # Teams overview with subquery counts
    agent_count_sq = (
        db.query(Agent.team_id, func.count(Agent.id).label("cnt"))
        .group_by(Agent.team_id)
        .subquery()
    )
    meeting_count_sq = (
        db.query(Meeting.team_id, func.count(Meeting.id).label("cnt"))
        .group_by(Meeting.team_id)
        .subquery()
    )
    teams_rows = (
        db.query(
            Team,
            func.coalesce(agent_count_sq.c.cnt, 0).label("agent_count"),
            func.coalesce(meeting_count_sq.c.cnt, 0).label("meeting_count"),
        )
        .outerjoin(agent_count_sq, Team.id == agent_count_sq.c.team_id)
        .outerjoin(meeting_count_sq, Team.id == meeting_count_sq.c.team_id)
        .order_by(Team.updated_at.desc())
        .all()
    )
    teams_overview = [
        {
            "id": team.id,
            "name": team.name,
            "description": team.description,
            "agent_count": agent_count,
            "meeting_count": meeting_count,
            "created_at": team.created_at.isoformat() if team.created_at else None,
        }
        for team, agent_count, meeting_count in teams_rows
    ]

    return {
        "total_teams": total_teams,
        "total_agents": total_agents,
        "total_meetings": total_meetings,
        "completed_meetings": completed_meetings,
        "total_artifacts": total_artifacts,
        "total_messages": total_messages,
        "recent_meetings": recent_meetings,
        "teams_overview": teams_overview,
    }
