from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Integer, JSON
from sqlalchemy.orm import relationship, backref
from datetime import datetime, UTC
import uuid
import enum

from app.database import Base


class MeetingStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    team_id = Column(String(36), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, default="")
    agenda = Column(Text, default="")
    agenda_questions = Column(JSON, default=list)
    agenda_rules = Column(JSON, default=list)
    output_type = Column(String(20), default="code")
    context_meeting_ids = Column(JSON, default=list)  # IDs of previous meetings to load context from
    participant_agent_ids = Column(JSON, default=list)  # If non-empty, only these agents join the meeting
    meeting_type = Column(String(20), default="team")  # "team" | "individual" | "merge"
    individual_agent_id = Column(String(36), ForeignKey("agents.id"), nullable=True)
    source_meeting_ids = Column(JSON, default=list)  # for merge: IDs of source meetings
    parent_meeting_id = Column(String(36), ForeignKey("meetings.id"), nullable=True)  # for rewrite
    rewrite_feedback = Column(Text, default="")
    agenda_strategy = Column(String(30), default="manual")  # manual|ai_auto|onboarding|agent_voting|chain
    status = Column(String(20), default=MeetingStatus.pending.value)
    max_rounds = Column(Integer, default=5)
    current_round = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Relationships
    team = relationship("Team", backref=backref("meetings", cascade="all, delete-orphan"))
    messages = relationship("MeetingMessage", back_populates="meeting", cascade="all, delete-orphan",
                          order_by="MeetingMessage.created_at")

    def __repr__(self):
        return f"<Meeting(id={self.id}, title={self.title}, status={self.status})>"


class MeetingMessage(Base):
    __tablename__ = "meeting_messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    meeting_id = Column(String(36), ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False)
    agent_id = Column(String(36), ForeignKey("agents.id"), nullable=True)  # None for user/system messages
    role = Column(String(20), nullable=False)  # user, assistant, system
    agent_name = Column(String(255), nullable=True)
    content = Column(Text, nullable=False)
    round_number = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    # Relationships
    meeting = relationship("Meeting", back_populates="messages")

    def __repr__(self):
        return f"<MeetingMessage(id={self.id}, role={self.role}, agent={self.agent_name})>"
