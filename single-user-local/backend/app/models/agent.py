from sqlalchemy import Column, String, Text, Float, ForeignKey, DateTime, Boolean, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, UTC
import uuid

from app.database import Base


class Agent(Base):
    __tablename__ = "agents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    team_id = Column(String(36), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)

    # Agent configuration
    name = Column(String(255), nullable=False)
    title = Column(String(255), nullable=False)
    expertise = Column(Text, nullable=False)
    goal = Column(Text, nullable=False)
    role = Column(Text, nullable=False)

    # System prompt (computed from above fields)
    system_prompt = Column(Text, nullable=False)

    # Model configuration
    model = Column(String(100), nullable=False)  # e.g., "gpt-4", "claude-3-opus"
    model_params = Column(JSON, default={})  # temperature, max_tokens, etc.

    # Visual editor position
    position_x = Column(Float, default=0.0)
    position_y = Column(Float, default=0.0)

    # Mirror agent fields
    is_mirror = Column(Boolean, default=False)
    primary_agent_id = Column(String(36), ForeignKey("agents.id"), nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Relationships
    team = relationship("Team", back_populates="agents")
    primary_agent = relationship("Agent", remote_side=[id], foreign_keys=[primary_agent_id])

    def __repr__(self):
        return f"<Agent(id={self.id}, name={self.name}, model={self.model})>"
