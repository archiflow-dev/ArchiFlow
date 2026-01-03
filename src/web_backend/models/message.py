"""
Message model for ArchiFlow Web Backend.

Represents chat messages in an agent session.
"""

from sqlalchemy import Column, String, DateTime, Enum, Text, ForeignKey, Integer
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
import uuid

from ..database.connection import Base


class MessageRole(str, enum.Enum):
    """Role of the message sender."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


def generate_message_id() -> str:
    """Generate a unique message ID."""
    return f"msg_{uuid.uuid4().hex[:12]}"


class Message(Base):
    """
    SQLAlchemy model for chat messages.

    Messages are associated with a session and ordered by sequence number.
    """
    __tablename__ = "messages"

    # Primary key
    id = Column(String(64), primary_key=True, default=generate_message_id)

    # Session association
    session_id = Column(
        String(64),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Message content
    role = Column(Enum(MessageRole), nullable=False)
    content = Column(Text, nullable=False)

    # Ordering within session
    sequence = Column(Integer, nullable=False, default=0)

    # Optional tool-related fields
    tool_name = Column(String(128), nullable=True)
    tool_call_id = Column(String(128), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    session = relationship("Session", back_populates="messages")

    def __repr__(self) -> str:
        content_preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"<Message(id={self.id}, role={self.role}, content='{content_preview}')>"

    def to_dict(self) -> dict:
        """Convert message to dictionary for API responses."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "role": self.role.value if self.role else None,
            "content": self.content,
            "sequence": self.sequence,
            "tool_name": self.tool_name,
            "tool_call_id": self.tool_call_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
