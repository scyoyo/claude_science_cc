import json
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List
import io

from app.database import get_db
from app.models import Meeting, CodeArtifact
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
