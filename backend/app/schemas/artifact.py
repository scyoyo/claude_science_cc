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

