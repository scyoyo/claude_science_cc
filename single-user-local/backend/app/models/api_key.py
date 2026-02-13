from sqlalchemy import Column, String, DateTime, Boolean
from datetime import datetime, UTC
import uuid

from app.database import Base


class APIKey(Base):
    __tablename__ = "api_keys"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    provider = Column(String(50), nullable=False)  # openai, anthropic, deepseek
    encrypted_key = Column(String(500), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    def __repr__(self):
        return f"<APIKey(id={self.id}, provider={self.provider})>"
