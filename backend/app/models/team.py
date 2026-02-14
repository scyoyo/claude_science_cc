from sqlalchemy import Column, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, UTC
import uuid

from app.database import Base


class Team(Base):
    __tablename__ = "teams"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    description = Column(Text)
    is_public = Column(Boolean, default=False)
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=True)  # Nullable for V1 compat
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Relationships
    agents = relationship("Agent", back_populates="team", cascade="all, delete-orphan", order_by="Agent.created_at")
    owner = relationship("User", foreign_keys=[owner_id])

    def __repr__(self):
        return f"<Team(id={self.id}, name={self.name})>"
