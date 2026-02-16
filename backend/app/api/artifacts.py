from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import Meeting, MeetingMessage, CodeArtifact
from app.schemas.artifact import (
    CodeArtifactCreate,
    CodeArtifactUpdate,
    CodeArtifactResponse,
    SmartExtractRequest,
    SmartExtractResponse,
    SmartExtractedFileResponse,
)
from app.schemas.pagination import PaginatedResponse
from app.core.code_extractor import extract_from_meeting_messages
from app.core.llm_code_extractor import LLMCodeExtractor
from app.api.deps import pagination_params, build_paginated_response

router = APIRouter(prefix="/artifacts", tags=["artifacts"])


@router.get("/meeting/{meeting_id}", response_model=PaginatedResponse[CodeArtifactResponse])
def list_meeting_artifacts(
    meeting_id: str,
    pagination: tuple[int, int] = Depends(pagination_params),
    db: Session = Depends(get_db),
):
    """List all code artifacts for a meeting with pagination."""
    skip, limit = pagination
    query = db.query(CodeArtifact).filter(CodeArtifact.meeting_id == meeting_id)
    return build_paginated_response(query, skip, limit)


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
    """Auto-extract code blocks from meeting messages and create artifacts.

    Uses regex-based extraction (fast but basic).
    For smarter extraction with LLM assistance, use /extract-smart endpoint.
    """
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


@router.post("/meeting/{meeting_id}/extract-smart", response_model=SmartExtractResponse, status_code=status.HTTP_201_CREATED)
async def extract_artifacts_smart(
    meeting_id: str,
    request: SmartExtractRequest = SmartExtractRequest(),
    db: Session = Depends(get_db),
):
    """Smart LLM-assisted code extraction with intelligent project organization.

    This endpoint uses LLM to:
    - Extract code even without standard markdown formatting
    - Infer project type and folder structure
    - Organize code into meaningful files and paths
    - Group related code together
    - Generate accurate dependency lists
    - Create README and requirements.txt

    Args:
        meeting_id: Meeting to extract code from
        request: Optional parameters (LLM model selection)

    Returns:
        SmartExtractResponse with project structure and organized code files
    """
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

    # Use LLM to extract and organize code
    extractor = LLMCodeExtractor(model=request.model)

    try:
        # Analyze project structure
        project_structure = await extractor.analyze_project_structure(msg_dicts)

        # Extract code with intelligent organization
        code_files = await extractor.extract_code_smart(msg_dicts, project_structure)

        # Generate requirements.txt if there are Python files
        requirements_txt = None
        if any(f.language in ("python", "py") for f in code_files):
            requirements_txt = await extractor.generate_smart_requirements(code_files)

        # Save artifacts to database
        artifacts = []
        for code_file in code_files:
            artifact = CodeArtifact(
                meeting_id=meeting_id,
                filename=code_file.filename,
                language=code_file.language,
                content=code_file.content,
                description=code_file.description,
            )
            db.add(artifact)
            artifacts.append(artifact)

        # Save README if generated
        if project_structure.readme_content:
            readme_artifact = CodeArtifact(
                meeting_id=meeting_id,
                filename="README.md",
                language="markdown",
                content=project_structure.readme_content,
                description="Auto-generated project documentation",
            )
            db.add(readme_artifact)
            artifacts.append(readme_artifact)

        # Save requirements.txt if generated
        if requirements_txt:
            req_artifact = CodeArtifact(
                meeting_id=meeting_id,
                filename="requirements.txt",
                language="text",
                content=requirements_txt,
                description="Auto-generated Python dependencies",
            )
            db.add(req_artifact)
            artifacts.append(req_artifact)

        db.commit()

        # Build response
        file_responses = [
            SmartExtractedFileResponse(
                filename=f.filename,
                language=f.language,
                content=f.content,
                description=f.description,
                dependencies=f.dependencies,
                source_agent=f.source_agent,
                related_files=f.related_files,
            )
            for f in code_files
        ]

        return SmartExtractResponse(
            project_type=project_structure.project_type,
            suggested_folders=project_structure.suggested_folders,
            entry_point=project_structure.entry_point,
            readme_content=project_structure.readme_content,
            files=file_responses,
            requirements_txt=requirements_txt,
        )

    except Exception as e:
        # If LLM extraction fails, fall back to basic extraction
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Smart extraction failed: {str(e)}. Try using /extract endpoint for basic regex extraction.",
        )
