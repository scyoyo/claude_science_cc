from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import WebhookConfig
from app.schemas.webhook import WebhookCreate, WebhookUpdate, WebhookResponse, VALID_EVENTS

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.get("/events")
def list_webhook_events():
    """List all supported webhook event types."""
    return VALID_EVENTS


@router.get("/", response_model=List[WebhookResponse])
def list_webhooks(db: Session = Depends(get_db)):
    """List all registered webhooks."""
    return db.query(WebhookConfig).all()


@router.post("/", response_model=WebhookResponse, status_code=status.HTTP_201_CREATED)
def create_webhook(data: WebhookCreate, db: Session = Depends(get_db)):
    """Register a new webhook."""
    # Validate event types
    invalid = [e for e in data.events if e not in VALID_EVENTS]
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid event types: {', '.join(invalid)}. Valid: {', '.join(VALID_EVENTS)}",
        )

    webhook = WebhookConfig(
        url=data.url,
        events=data.events,
        secret=data.secret,
    )
    db.add(webhook)
    db.commit()
    db.refresh(webhook)
    return webhook


@router.get("/{webhook_id}", response_model=WebhookResponse)
def get_webhook(webhook_id: str, db: Session = Depends(get_db)):
    """Get a specific webhook."""
    webhook = db.query(WebhookConfig).filter(WebhookConfig.id == webhook_id).first()
    if not webhook:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
    return webhook


@router.put("/{webhook_id}", response_model=WebhookResponse)
def update_webhook(webhook_id: str, data: WebhookUpdate, db: Session = Depends(get_db)):
    """Update a webhook."""
    webhook = db.query(WebhookConfig).filter(WebhookConfig.id == webhook_id).first()
    if not webhook:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")

    update_data = data.model_dump(exclude_unset=True)
    if "events" in update_data:
        invalid = [e for e in update_data["events"] if e not in VALID_EVENTS]
        if invalid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid event types: {', '.join(invalid)}",
            )

    for field, value in update_data.items():
        setattr(webhook, field, value)

    db.commit()
    db.refresh(webhook)
    return webhook


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_webhook(webhook_id: str, db: Session = Depends(get_db)):
    """Delete a webhook."""
    webhook = db.query(WebhookConfig).filter(WebhookConfig.id == webhook_id).first()
    if not webhook:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
    db.delete(webhook)
    db.commit()
    return None
