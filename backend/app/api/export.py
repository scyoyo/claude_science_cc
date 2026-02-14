import json
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List
import io

from app.database import get_db
from app.models import Meeting, MeetingMessage, CodeArtifact, Agent
from app.core.exporter import export_as_zip, export_as_colab_notebook, export_as_github_files

router = APIRouter(prefix="/export", tags=["export"])


def _get_artifacts(meeting_id: str, db: Session) -> tuple:
    """Get meeting and its artifacts."""
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")

    artifacts = db.query(CodeArtifact).filter(
        CodeArtifact.meeting_id == meeting_id,
    ).all()

    artifact_dicts = [
        {
            "filename": a.filename,
            "language": a.language,
            "content": a.content,
            "description": a.description,
        }
        for a in artifacts
    ]

    return meeting, artifact_dicts


@router.get("/meeting/{meeting_id}/json")
def export_json(meeting_id: str, db: Session = Depends(get_db)):
    """Export complete meeting data as JSON.

    Returns structured JSON with meeting metadata, team, agents, messages,
    artifacts, and summary (last agent message).
    """
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")

    # Get messages
    messages = db.query(MeetingMessage).filter(
        MeetingMessage.meeting_id == meeting_id,
    ).order_by(MeetingMessage.created_at).all()

    # Get artifacts
    artifacts = db.query(CodeArtifact).filter(
        CodeArtifact.meeting_id == meeting_id,
    ).all()

    # Get team agents
    agents = db.query(Agent).filter(
        Agent.team_id == meeting.team_id,
        Agent.is_mirror == False,
    ).all()

    # Extract summary: last assistant message
    summary = ""
    for msg in reversed(messages):
        if msg.role == "assistant":
            summary = msg.content
            break

    result = {
        "meeting": {
            "id": meeting.id,
            "title": meeting.title,
            "description": meeting.description,
            "agenda": meeting.agenda,
            "agenda_questions": meeting.agenda_questions or [],
            "agenda_rules": meeting.agenda_rules or [],
            "output_type": meeting.output_type,
            "status": meeting.status,
            "max_rounds": meeting.max_rounds,
            "current_round": meeting.current_round,
            "context_meeting_ids": meeting.context_meeting_ids or [],
            "created_at": meeting.created_at.isoformat() if meeting.created_at else None,
            "updated_at": meeting.updated_at.isoformat() if meeting.updated_at else None,
        },
        "team": {
            "id": meeting.team_id,
            "name": meeting.team.name if meeting.team else None,
        },
        "agents": [
            {
                "name": a.name,
                "title": a.title,
                "expertise": a.expertise,
                "role": a.role,
                "model": a.model,
            }
            for a in agents
        ],
        "messages": [
            {
                "role": m.role,
                "agent_name": m.agent_name,
                "content": m.content,
                "round_number": m.round_number,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
        "artifacts": [
            {
                "filename": a.filename,
                "language": a.language,
                "content": a.content,
            }
            for a in artifacts
        ],
        "summary": summary,
    }

    json_bytes = json.dumps(result, indent=2, ensure_ascii=False).encode("utf-8")
    return StreamingResponse(
        io.BytesIO(json_bytes),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{meeting.title.replace(" ", "_")}.json"'},
    )


@router.get("/meeting/{meeting_id}/zip")
def export_zip(meeting_id: str, db: Session = Depends(get_db)):
    """Download meeting artifacts as a ZIP file."""
    meeting, artifact_dicts = _get_artifacts(meeting_id, db)

    if not artifact_dicts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No code artifacts to export. Extract code first.",
        )

    zip_bytes = export_as_zip(artifact_dicts, project_name=meeting.title.replace(" ", "_"))

    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{meeting.title.replace(" ", "_")}.zip"'},
    )


@router.get("/meeting/{meeting_id}/notebook")
def export_notebook(meeting_id: str, db: Session = Depends(get_db)):
    """Download meeting artifacts as a Colab notebook (.ipynb)."""
    meeting, artifact_dicts = _get_artifacts(meeting_id, db)

    if not artifact_dicts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No code artifacts to export. Extract code first.",
        )

    notebook = export_as_colab_notebook(artifact_dicts, project_name=meeting.title)
    notebook_json = json.dumps(notebook, indent=2)

    return StreamingResponse(
        io.BytesIO(notebook_json.encode()),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{meeting.title.replace(" ", "_")}.ipynb"'},
    )


@router.get("/meeting/{meeting_id}/github")
def export_github(meeting_id: str, db: Session = Depends(get_db)):
    """Get meeting artifacts in GitHub-ready format.

    Returns a list of files with paths and content that can be pushed to GitHub.
    """
    meeting, artifact_dicts = _get_artifacts(meeting_id, db)

    if not artifact_dicts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No code artifacts to export. Extract code first.",
        )

    files = export_as_github_files(artifact_dicts, project_name=meeting.title)
    return {"project_name": meeting.title, "files": files}
