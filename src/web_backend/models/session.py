"""
Session model for ArchiFlow Web Backend.

Represents an agent session with workflow state and metadata.
"""

from sqlalchemy import Column, String, DateTime, Enum, JSON, Text
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
import uuid

from ..database.connection import Base


class SessionStatus(str, enum.Enum):
    """Status of an agent session."""
    CREATED = "created"      # Session created, not yet started
    RUNNING = "running"      # Agent is actively processing
    PAUSED = "paused"        # User paused the session
    AWAITING_INPUT = "awaiting_input"  # Waiting for user input/approval
    COMPLETED = "completed"  # Session finished successfully
    FAILED = "failed"        # Session failed with error


def generate_session_id() -> str:
    """Generate a unique session ID."""
    return f"session_{uuid.uuid4().hex[:12]}"


class Session(Base):
    """
    SQLAlchemy model for agent sessions.

    A session represents a single conversation/workflow with an agent.
    """
    __tablename__ = "sessions"

    # Primary key
    id = Column(String(64), primary_key=True, default=generate_session_id)

    # Session configuration
    agent_type = Column(String(64), nullable=False, index=True)
    user_prompt = Column(Text, nullable=False)
    project_directory = Column(String(512), nullable=True)

    # Status tracking
    status = Column(
        Enum(SessionStatus),
        default=SessionStatus.CREATED,
        nullable=False,
        index=True
    )

    # Workflow state (JSON blob for flexible agent-specific state)
    workflow_state = Column(JSON, nullable=True, default=dict)

    # User association (for future multi-user support)
    user_id = Column(String(64), nullable=True, index=True, default="default_user")

    # Workspace tracking
    workspace_path = Column(String(512), nullable=True)
    workspace_deleted = Column(String(1), default="N")  # Y/N flag

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    # Relationships
    messages = relationship(
        "Message",
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Session(id={self.id}, agent_type={self.agent_type}, status={self.status})>"

    def to_dict(self) -> dict:
        """Convert session to dictionary for API responses."""
        return {
            "id": self.id,
            "agent_type": self.agent_type,
            "user_prompt": self.user_prompt,
            "project_directory": self.project_directory,
            "status": self.status.value if self.status else None,
            "workflow_state": self.workflow_state,
            "user_id": self.user_id,
            "workspace_path": self.workspace_path,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
