from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Optional


class APIKeyCreate(BaseModel):
    provider: str = Field(..., pattern="^(openai|anthropic|deepseek)$")
    api_key: str = Field(..., min_length=1)


class APIKeyUpdate(BaseModel):
    api_key: Optional[str] = Field(None, min_length=1)
    is_active: Optional[bool] = None


class APIKeyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    provider: str
    is_active: bool
    key_preview: str  # Last 4 chars, e.g., "...abcd"
    created_at: datetime
    updated_at: datetime
