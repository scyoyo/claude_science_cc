from sqlalchemy import Column, String, DateTime, Boolean
from datetime import datetime
import uuid

from app.database import Base


class APIKey(Base):
    __tablename__ = "api_keys"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    provider = Column(String(50), nullable=False)  # openai, anthropic, deepseek
    encrypted_key = Column(String(500), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<APIKey(id={self.id}, provider={self.provider})>"
