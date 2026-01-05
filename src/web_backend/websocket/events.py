"""
WebSocket event types and utilities.

Defines event types and helper functions for WebSocket communication.
"""

from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timezone


class EventType(str, Enum):
    """Types of WebSocket events."""

    # Connection events
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"

    # Session events
    SESSION_CREATED = "session_created"
    SESSION_STARTED = "session_started"
    SESSION_PAUSED = "session_paused"
    SESSION_RESUMED = "session_resumed"
    SESSION_COMPLETED = "session_completed"
    SESSION_FAILED = "session_failed"

    # Workflow events
    PHASE_STARTED = "phase_started"
    PHASE_COMPLETED = "phase_completed"
    PHASE_AWAITING_APPROVAL = "phase_awaiting_approval"
    PHASE_APPROVED = "phase_approved"
    PHASE_REJECTED = "phase_rejected"
    WORKFLOW_UPDATE = "workflow_update"

    # Agent events
    AGENT_THINKING = "agent_thinking"
    AGENT_TOOL_CALL = "agent_tool_call"
    AGENT_TOOL_RESULT = "agent_tool_result"
    AGENT_MESSAGE = "agent_message"
    AGENT_ERROR = "agent_error"

    # Artifact events
    ARTIFACT_CREATED = "artifact_created"
    ARTIFACT_UPDATED = "artifact_updated"
    ARTIFACT_DELETED = "artifact_deleted"

    # Message events
    MESSAGE_RECEIVED = "message_received"
    MESSAGE_STREAMING = "message_streaming"
    MESSAGE_COMPLETE = "message_complete"

    # Error events
    ERROR = "error"


class WebSocketEvent(BaseModel):
    """Base model for WebSocket events."""

    type: EventType = Field(..., description="Event type")
    session_id: Optional[str] = Field(None, description="Associated session ID")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    payload: Dict[str, Any] = Field(default_factory=dict)

    model_config = {
        "use_enum_values": True,
    }


class SessionEvent(WebSocketEvent):
    """Event related to session lifecycle."""

    session_id: str = Field(..., description="Session ID")
    status: Optional[str] = Field(None, description="New session status")


class WorkflowEvent(WebSocketEvent):
    """Event related to workflow state changes."""

    session_id: str = Field(..., description="Session ID")
    phase_id: Optional[str] = Field(None, description="Phase ID")
    progress_percent: Optional[float] = Field(None, description="Overall progress")


class AgentEvent(WebSocketEvent):
    """Event from agent execution."""

    session_id: str = Field(..., description="Session ID")
    agent_type: Optional[str] = Field(None, description="Agent type")


class ArtifactEvent(WebSocketEvent):
    """Event related to artifact changes."""

    session_id: str = Field(..., description="Session ID")
    artifact_path: str = Field(..., description="Path to artifact")
    artifact_type: Optional[str] = Field(None, description="MIME type")


class MessageEvent(WebSocketEvent):
    """Event for chat messages."""

    session_id: str = Field(..., description="Session ID")
    message_id: Optional[str] = Field(None, description="Message ID")
    role: Optional[str] = Field(None, description="Message role")
    content: Optional[str] = Field(None, description="Message content or chunk")
    is_complete: bool = Field(False, description="Whether message is complete")


class ErrorEvent(WebSocketEvent):
    """Error event."""

    type: EventType = EventType.ERROR
    error_code: Optional[str] = Field(None, description="Error code")
    error_message: str = Field(..., description="Error message")
    recoverable: bool = Field(True, description="Whether error is recoverable")


def create_event(
    event_type: EventType,
    session_id: Optional[str] = None,
    **payload
) -> Dict[str, Any]:
    """
    Create a WebSocket event dictionary.

    Args:
        event_type: Type of event
        session_id: Optional session ID
        **payload: Event payload

    Returns:
        Event dictionary ready to send
    """
    return {
        "type": event_type.value,
        "session_id": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }
