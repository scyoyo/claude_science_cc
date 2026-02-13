from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import Meeting, MeetingMessage, CodeArtifact
from app.schemas.artifact import CodeArtifactCreate, CodeArtifactUpdate, CodeArtifactResponse
from app.core.code_extractor import extract_from_meeting_messages

router = APIRouter(prefix="/artifacts", tags=["artifacts"])


@router.get("/meeting/{meeting_id}", response_model=List[CodeArtifactResponse])
def list_meeting_artifacts(meeting_id: str, db: Session = Depends(get_db)):
    """List all code artifacts for a meeting."""
    return db.query(CodeArtifact).filter(CodeArtifact.meeting_id == meeting_id).all()


@router.get("/{artifact_id}", response_model=CodeArtifactResponse)
def get_artifact(artifact_id: str, db: Session = Depends(get_db)):
    """Get a specific code artifact."""
    artifact = db.query(CodeArtifact).filter(CodeArtifact.id == artifact_id).first()
    if not artifact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")
    return artifact


@router.post("/", response_model=CodeArtifactResponse, status_code=status.HTTP_201_CREATED)
def create_artifact(data: CodeArtifactCreate, db: Session = Depends(get_db)):
    """Create a code artifact manually."""
    meeting = db.query(Meeting).filter(Meeting.id == data.meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")

    artifact = CodeArtifact(**data.model_dump())
    db.add(artifact)
    db.commit()
    db.refresh(artifact)
    return artifact


@router.put("/{artifact_id}", response_model=CodeArtifactResponse)
def update_artifact(artifact_id: str, data: CodeArtifactUpdate, db: Session = Depends(get_db)):
    """Update a code artifact."""
    artifact = db.query(CodeArtifact).filter(CodeArtifact.id == artifact_id).first()
    if not artifact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(artifact, field, value)

    if "content" in update_data:
        artifact.version += 1

    db.commit()
    db.refresh(artifact)
    return artifact


@router.delete("/{artifact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_artifact(artifact_id: str, db: Session = Depends(get_db)):
    """Delete a code artifact."""
    artifact = db.query(CodeArtifact).filter(CodeArtifact.id == artifact_id).first()
    if not artifact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")

    db.delete(artifact)
    db.commit()
    return None


@router.post("/meeting/{meeting_id}/extract", response_model=List[CodeArtifactResponse], status_code=status.HTTP_201_CREATED)
def extract_artifacts(meeting_id: str, db: Session = Depends(get_db)):
    """Auto-extract code blocks from meeting messages and create artifacts."""
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")

    messages = db.query(MeetingMessage).filter(
        MeetingMessage.meeting_id == meeting_id,
    ).order_by(MeetingMessage.created_at).all()

    msg_dicts = [
        {"content": m.content, "agent_name": m.agent_name, "role": m.role}
        for m in messages
    ]

    extracted = extract_from_meeting_messages(msg_dicts)
    if not extracted:
        return []

    artifacts = []
    for code in extracted:
        artifact = CodeArtifact(
            meeting_id=meeting_id,
            filename=code.suggested_filename,
            language=code.language,
            content=code.content,
            description=f"Extracted from {code.source_agent or 'meeting'}" if code.source_agent else "",
        )
        db.add(artifact)
        artifacts.append(artifact)

    db.commit()
    for a in artifacts:
        db.refresh(a)
    return artifacts
