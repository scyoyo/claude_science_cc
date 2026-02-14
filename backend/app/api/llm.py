from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, List

from app.config import settings
from app.database import get_db
from app.models import APIKey
from app.schemas.api_key import APIKeyCreate, APIKeyUpdate, APIKeyResponse
from app.core.encryption import encrypt_api_key, decrypt_api_key
from app.core.llm_client import (
    LLMResponse,
    create_provider,
    detect_provider,
    PROVIDER_MAP,
)
from app.schemas.onboarding import ChatMessage


class LLMChatRequest(BaseModel):
    model: str = Field(..., min_length=1)
    messages: List[ChatMessage]
    params: Dict = {}

router = APIRouter(prefix="/llm", tags=["llm"])


def _key_preview(encrypted_key: str) -> str:
    """Get a safe preview of an encrypted API key."""
    try:
        decrypted = decrypt_api_key(encrypted_key, settings.ENCRYPTION_SECRET)
        return f"...{decrypted[-4:]}"
    except Exception:
        return "...????"


def _to_response(key: APIKey) -> dict:
    """Convert APIKey model to response dict with key_preview."""
    return {
        "id": key.id,
        "provider": key.provider,
        "is_active": key.is_active,
        "key_preview": _key_preview(key.encrypted_key),
        "created_at": key.created_at,
        "updated_at": key.updated_at,
    }


# --- API Key Management ---


@router.get("/api-keys", response_model=List[APIKeyResponse])
def list_api_keys(db: Session = Depends(get_db)):
    """List all stored API keys (keys are masked)."""
    keys = db.query(APIKey).all()
    return [_to_response(k) for k in keys]


@router.post("/api-keys", response_model=APIKeyResponse, status_code=status.HTTP_201_CREATED)
def create_api_key(data: APIKeyCreate, db: Session = Depends(get_db)):
    """Store a new API key (encrypted)."""
    # Check for existing active key for this provider
    existing = db.query(APIKey).filter(
        APIKey.provider == data.provider,
        APIKey.is_active == True,
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Active API key already exists for provider '{data.provider}'. "
                   "Deactivate or delete it first.",
        )

    encrypted = encrypt_api_key(data.api_key, settings.ENCRYPTION_SECRET)
    key = APIKey(provider=data.provider, encrypted_key=encrypted)
    db.add(key)
    db.commit()
    db.refresh(key)
    return _to_response(key)


@router.put("/api-keys/{key_id}", response_model=APIKeyResponse)
def update_api_key(key_id: str, data: APIKeyUpdate, db: Session = Depends(get_db)):
    """Update an API key."""
    key = db.query(APIKey).filter(APIKey.id == key_id).first()
    if not key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

    if data.api_key is not None:
        key.encrypted_key = encrypt_api_key(data.api_key, settings.ENCRYPTION_SECRET)
    if data.is_active is not None:
        key.is_active = data.is_active

    db.commit()
    db.refresh(key)
    return _to_response(key)


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_api_key(key_id: str, db: Session = Depends(get_db)):
    """Delete an API key."""
    key = db.query(APIKey).filter(APIKey.id == key_id).first()
    if not key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

    db.delete(key)
    db.commit()
    return None


# --- LLM Chat ---


@router.get("/providers")
def list_providers():
    """List available LLM providers."""
    return {"providers": list(PROVIDER_MAP.keys())}


@router.post("/chat")
def llm_chat(
    request: LLMChatRequest,
    db: Session = Depends(get_db),
):
    """Send a chat request to an LLM provider.

    Automatically detects the provider from the model name and uses the stored API key.
    """
    # Detect provider
    provider_name = detect_provider(request.model)

    # Get API key: DB first, then env var fallback
    api_key_record = db.query(APIKey).filter(
        APIKey.provider == provider_name,
        APIKey.is_active == True,
    ).first()

    if api_key_record:
        decrypted_key = decrypt_api_key(api_key_record.encrypted_key, settings.ENCRYPTION_SECRET)
    else:
        # Fallback to environment variable
        env_keys = {"openai": settings.OPENAI_API_KEY, "anthropic": settings.ANTHROPIC_API_KEY, "deepseek": settings.DEEPSEEK_API_KEY}
        decrypted_key = env_keys.get(provider_name, "")
        if not decrypted_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No active API key found for provider '{provider_name}'. "
                       "Add one via POST /api/llm/api-keys or set the environment variable.",
            )

    provider = create_provider(provider_name, decrypted_key)

    try:
        response = provider.chat(request.messages, request.model, request.params)
        return {
            "content": response.content,
            "model": response.model,
            "provider": response.provider,
            "usage": response.usage,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM request failed: {str(e)}",
        )
