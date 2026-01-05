"""
Session event emitter for WebSocket communication.

Bridges WebSessionBroker with Socket.IO server to emit real-time events.
"""

from typing import Dict, Any, Optional, TYPE_CHECKING
import logging
from datetime import datetime, timezone

from .events import EventType, create_event

if TYPE_CHECKING:
    from .server import sio

logger = logging.getLogger(__name__)


class SessionEmitter:
    """
    Emits session events to connected WebSocket clients.

    Used as the ws_callback for WebSessionBroker to forward
    agent events to the frontend in real-time.

    Usage:
        emitter = SessionEmitter(session_id)
        broker = WebSessionBroker(
            session_id=session_id,
            ws_callback=emitter.emit_event,
            ...
        )
    """

    def __init__(self, session_id: str):
        """
        Initialize the session emitter.

        Args:
            session_id: Session ID for this emitter
        """
        self.session_id = session_id
        self._message_buffer: list[Dict[str, Any]] = []
        self._is_streaming = False

    async def emit_event(self, event: Dict[str, Any]) -> None:
        """
        Emit an event to all clients subscribed to this session.

        This is the callback passed to WebSessionBroker.

        Args:
            event: Event dictionary from WebSessionBroker._transform_to_ws_event
        """
        # Import here to avoid circular imports
        from .server import emit_to_session

        event_type = event.get("type", "unknown")

        try:
            # Map internal event types to Socket.IO events
            if event_type == "agent_message":
                await self._emit_agent_message(event)
            elif event_type == "tool_call":
                await self._emit_tool_call(event)
            elif event_type == "tool_result":
                await self._emit_tool_result(event)
            elif event_type == "agent_thought":
                await self._emit_agent_thought(event)
            elif event_type == "waiting_for_input":
                await self._emit_waiting_for_input(event)
            elif event_type == "agent_finished":
                await self._emit_agent_finished(event)
            elif event_type == "refinement_applied":
                await self._emit_refinement_applied(event)
            else:
                # Generic event emission
                await emit_to_session(
                    self.session_id,
                    "agent_event",
                    {
                        "type": event_type,
                        "session_id": self.session_id,
                        "payload": event,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )

            logger.debug(f"Emitted {event_type} event for session {self.session_id}")

        except Exception as e:
            logger.error(f"Error emitting event: {e}", exc_info=True)

    async def _emit_agent_message(self, event: Dict[str, Any]) -> None:
        """Emit an agent message event."""
        from .server import emit_message

        await emit_message(self.session_id, {
            "id": f"msg_{event.get('sequence', 0)}",
            "role": "assistant",
            "content": event.get("content", ""),
            "sequence": event.get("sequence", 0),
            "timestamp": event.get("timestamp") or datetime.now(timezone.utc).isoformat(),
            "is_streaming": False,
            "is_complete": True,
        })

    async def _emit_tool_call(self, event: Dict[str, Any]) -> None:
        """Emit a tool call event."""
        from .server import emit_agent_event

        await emit_agent_event(self.session_id, EventType.AGENT_TOOL_CALL.value, {
            "tool_name": event.get("tool_name", ""),
            "arguments": event.get("arguments", {}),
            "content": event.get("content", ""),
        })

    async def _emit_tool_result(self, event: Dict[str, Any]) -> None:
        """Emit a tool result event."""
        from .server import emit_agent_event

        await emit_agent_event(self.session_id, EventType.AGENT_TOOL_RESULT.value, {
            "tool_name": event.get("tool_name", ""),
            "result": event.get("result", ""),
            "status": event.get("status", "success"),
            "metadata": event.get("metadata", {}),
        })

        # Check if this was a file operation for artifact updates
        tool_name = event.get("tool_name", "")
        if tool_name in ("write_file", "edit_file", "create_file"):
            await self._emit_artifact_update(event, "created" if tool_name == "create_file" else "updated")

    async def _emit_artifact_update(self, event: Dict[str, Any], action: str) -> None:
        """Emit an artifact update event."""
        from .server import emit_artifact_update

        # Extract path from tool arguments or result
        metadata = event.get("metadata", {})
        path = metadata.get("path") or event.get("arguments", {}).get("path", "")

        if path:
            await emit_artifact_update(self.session_id, path, action)

    async def _emit_agent_thought(self, event: Dict[str, Any]) -> None:
        """Emit an agent thinking event."""
        from .server import emit_agent_event

        await emit_agent_event(self.session_id, EventType.AGENT_THINKING.value, {
            "content": event.get("content", ""),
        })

    async def _emit_waiting_for_input(self, event: Dict[str, Any]) -> None:
        """Emit waiting for user input event."""
        from .server import emit_to_session

        await emit_to_session(self.session_id, "waiting_for_input", {
            "session_id": self.session_id,
            "sequence": event.get("sequence", 0),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    async def _emit_agent_finished(self, event: Dict[str, Any]) -> None:
        """Emit agent finished event."""
        from .server import emit_to_session

        await emit_to_session(self.session_id, "agent_finished", {
            "session_id": self.session_id,
            "reason": event.get("reason", "completed"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    async def _emit_refinement_applied(self, event: Dict[str, Any]) -> None:
        """Emit refinement notification event."""
        from .server import emit_to_session

        await emit_to_session(self.session_id, "refinement_applied", {
            "session_id": self.session_id,
            "content": event.get("content", ""),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })


class StreamingMessageEmitter:
    """
    Handles streaming message emission with buffering.

    For streaming LLM responses, this buffers tokens and emits
    chunks at regular intervals for smooth frontend rendering.
    """

    def __init__(self, session_id: str, message_id: str):
        """
        Initialize streaming emitter.

        Args:
            session_id: Session ID
            message_id: Unique message ID for this stream
        """
        self.session_id = session_id
        self.message_id = message_id
        self._buffer: str = ""
        self._total_content: str = ""
        self._chunk_size = 50  # Characters per chunk
        self._is_complete = False

    async def append(self, content: str) -> None:
        """
        Append content to the stream buffer.

        Emits chunks when buffer reaches chunk size.

        Args:
            content: Content to append
        """
        self._buffer += content
        self._total_content += content

        # Emit when buffer reaches chunk size
        if len(self._buffer) >= self._chunk_size:
            await self._emit_chunk()

    async def _emit_chunk(self) -> None:
        """Emit buffered content as a chunk."""
        if not self._buffer:
            return

        from .server import emit_to_session

        await emit_to_session(self.session_id, "message_chunk", {
            "session_id": self.session_id,
            "message_id": self.message_id,
            "chunk": self._buffer,
            "is_complete": False,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        self._buffer = ""

    async def complete(self) -> None:
        """
        Complete the stream and emit final message.

        Flushes any remaining buffer and sends completion signal.
        """
        # Flush remaining buffer
        if self._buffer:
            await self._emit_chunk()

        from .server import emit_message

        # Emit complete message
        await emit_message(self.session_id, {
            "id": self.message_id,
            "role": "assistant",
            "content": self._total_content,
            "is_streaming": False,
            "is_complete": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        self._is_complete = True

    @property
    def is_complete(self) -> bool:
        """Check if stream is complete."""
        return self._is_complete

    @property
    def content(self) -> str:
        """Get total content streamed so far."""
        return self._total_content


# Helper functions for workflow events

async def emit_workflow_phase_started(session_id: str, phase_id: str, phase_name: str) -> None:
    """Emit phase started event."""
    from .server import emit_to_session

    await emit_to_session(session_id, "workflow_update", create_event(
        EventType.PHASE_STARTED,
        session_id=session_id,
        phase_id=phase_id,
        phase_name=phase_name,
    ))


async def emit_workflow_phase_awaiting(session_id: str, phase_id: str, phase_name: str) -> None:
    """Emit phase awaiting approval event."""
    from .server import emit_to_session

    await emit_to_session(session_id, "workflow_update", create_event(
        EventType.PHASE_AWAITING_APPROVAL,
        session_id=session_id,
        phase_id=phase_id,
        phase_name=phase_name,
    ))


async def emit_workflow_phase_approved(session_id: str, phase_id: str, next_phase_id: Optional[str] = None) -> None:
    """Emit phase approved event."""
    from .server import emit_to_session

    await emit_to_session(session_id, "workflow_update", create_event(
        EventType.PHASE_APPROVED,
        session_id=session_id,
        phase_id=phase_id,
        next_phase=next_phase_id,
    ))


async def emit_workflow_phase_rejected(session_id: str, phase_id: str, feedback: str) -> None:
    """Emit phase rejected event."""
    from .server import emit_to_session

    await emit_to_session(session_id, "workflow_update", create_event(
        EventType.PHASE_REJECTED,
        session_id=session_id,
        phase_id=phase_id,
        feedback=feedback,
    ))


async def emit_session_status_change(session_id: str, status: str) -> None:
    """Emit session status change event."""
    from .server import emit_to_session

    event_map = {
        "running": EventType.SESSION_STARTED,
        "paused": EventType.SESSION_PAUSED,
        "completed": EventType.SESSION_COMPLETED,
        "failed": EventType.SESSION_FAILED,
    }

    event_type = event_map.get(status, EventType.SESSION_STARTED)

    await emit_to_session(session_id, "session_update", create_event(
        event_type,
        session_id=session_id,
        status=status,
    ))
