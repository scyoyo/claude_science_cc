from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import List, Optional


class CodeArtifactCreate(BaseModel):
    meeting_id: str
    filename: str = Field(..., min_length=1, max_length=255)
    language: str = "python"
    content: str
    description: str = ""


class CodeArtifactUpdate(BaseModel):
    filename: Optional[str] = Field(None, min_length=1, max_length=255)
    language: Optional[str] = None
    content: Optional[str] = None
    description: Optional[str] = None


class CodeArtifactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    meeting_id: str
    filename: str
    language: str
    content: str
    description: Optional[str] = ""
    version: int
    created_at: datetime
    updated_at: datetime


class SmartExtractRequest(BaseModel):
    """Request parameters for smart LLM-assisted extraction (no model selection)."""
    pass


class SmartExtractedFileResponse(BaseModel):
    """Response for a single extracted file with LLM-enhanced metadata."""
    filename: str
    language: str
    content: str
    description: str
    dependencies: List[str] = []
    source_agent: Optional[str] = None
    related_files: List[str] = []


class SmartExtractResponse(BaseModel):
    """Response for smart extraction endpoint."""
    project_type: str
    suggested_folders: List[str]
    entry_point: Optional[str] = None
    readme_content: Optional[str] = None
    files: List[SmartExtractedFileResponse]
    requirements_txt: Optional[str] = None
