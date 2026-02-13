from sqlalchemy import Column, String, Boolean, DateTime, JSON
from datetime import datetime, UTC
import uuid

from app.database import Base


class WebhookConfig(Base):
    __tablename__ = "webhook_configs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    url = Column(String(2048), nullable=False)
    events = Column(JSON, nullable=False, default=list)  # e.g. ["meeting.completed", "artifact.created"]
    is_active = Column(Boolean, default=True)
    secret = Column(String(255), nullable=True)  # Optional HMAC secret for signature verification
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    def __repr__(self):
        return f"<WebhookConfig(id={self.id}, url={self.url}, active={self.is_active})>"
