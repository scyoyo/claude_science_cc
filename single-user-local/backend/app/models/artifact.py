from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Integer
from datetime import datetime, UTC
import uuid

from app.database import Base


class CodeArtifact(Base):
    __tablename__ = "code_artifacts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    meeting_id = Column(String(36), ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String(255), nullable=False)
    language = Column(String(50), default="python")
    content = Column(Text, nullable=False)
    description = Column(Text, default="")
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    def __repr__(self):
        return f"<CodeArtifact(id={self.id}, filename={self.filename})>"
