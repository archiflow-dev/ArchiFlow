"""
Tests for WebSocket functionality.

Tests the Socket.IO server, connection manager, events, and session emitter.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

# Test the events module
from src.web_backend.websocket.events import (
    EventType,
    WebSocketEvent,
    SessionEvent,
    WorkflowEvent,
    AgentEvent,
    ArtifactEvent,
    MessageEvent,
    ErrorEvent,
    create_event,
)

# Test the connection manager
from src.web_backend.websocket.manager import (
    ConnectionManager,
    ClientInfo,
)


class TestEventType:
    """Test EventType enum."""

    def test_connection_events(self):
        """Test connection event types."""
        assert EventType.CONNECTED == "connected"
        assert EventType.DISCONNECTED == "disconnected"

    def test_session_events(self):
        """Test session event types."""
        assert EventType.SESSION_CREATED == "session_created"
        assert EventType.SESSION_STARTED == "session_started"
        assert EventType.SESSION_PAUSED == "session_paused"
        assert EventType.SESSION_RESUMED == "session_resumed"
        assert EventType.SESSION_COMPLETED == "session_completed"
        assert EventType.SESSION_FAILED == "session_failed"

    def test_workflow_events(self):
        """Test workflow event types."""
        assert EventType.PHASE_STARTED == "phase_started"
        assert EventType.PHASE_COMPLETED == "phase_completed"
        assert EventType.PHASE_AWAITING_APPROVAL == "phase_awaiting_approval"
        assert EventType.PHASE_APPROVED == "phase_approved"
        assert EventType.PHASE_REJECTED == "phase_rejected"

    def test_agent_events(self):
        """Test agent event types."""
        assert EventType.AGENT_THINKING == "agent_thinking"
        assert EventType.AGENT_TOOL_CALL == "agent_tool_call"
        assert EventType.AGENT_TOOL_RESULT == "agent_tool_result"
        assert EventType.AGENT_MESSAGE == "agent_message"
        assert EventType.AGENT_ERROR == "agent_error"

    def test_artifact_events(self):
        """Test artifact event types."""
        assert EventType.ARTIFACT_CREATED == "artifact_created"
        assert EventType.ARTIFACT_UPDATED == "artifact_updated"
        assert EventType.ARTIFACT_DELETED == "artifact_deleted"

    def test_message_events(self):
        """Test message event types."""
        assert EventType.MESSAGE_RECEIVED == "message_received"
        assert EventType.MESSAGE_STREAMING == "message_streaming"
        assert EventType.MESSAGE_COMPLETE == "message_complete"


class TestWebSocketEvent:
    """Test WebSocketEvent model."""

    def test_create_basic_event(self):
        """Test creating a basic event."""
        event = WebSocketEvent(type=EventType.CONNECTED)

        assert event.type == EventType.CONNECTED
        assert event.session_id is None
        assert event.payload == {}
        assert event.timestamp is not None

    def test_create_event_with_session(self):
        """Test creating an event with session ID."""
        event = WebSocketEvent(
            type=EventType.SESSION_STARTED,
            session_id="session-123",
            payload={"status": "running"},
        )

        assert event.type == EventType.SESSION_STARTED
        assert event.session_id == "session-123"
        assert event.payload == {"status": "running"}


class TestSessionEvent:
    """Test SessionEvent model."""

    def test_create_session_event(self):
        """Test creating a session event."""
        event = SessionEvent(
            type=EventType.SESSION_STARTED,
            session_id="session-123",
            status="running",
        )

        assert event.type == EventType.SESSION_STARTED
        assert event.session_id == "session-123"
        assert event.status == "running"


class TestWorkflowEvent:
    """Test WorkflowEvent model."""

    def test_create_workflow_event(self):
        """Test creating a workflow event."""
        event = WorkflowEvent(
            type=EventType.PHASE_COMPLETED,
            session_id="session-123",
            phase_id="phase-1",
            progress_percent=50.0,
        )

        assert event.type == EventType.PHASE_COMPLETED
        assert event.phase_id == "phase-1"
        assert event.progress_percent == 50.0


class TestAgentEvent:
    """Test AgentEvent model."""

    def test_create_agent_event(self):
        """Test creating an agent event."""
        event = AgentEvent(
            type=EventType.AGENT_MESSAGE,
            session_id="session-123",
            agent_type="coding",
        )

        assert event.type == EventType.AGENT_MESSAGE
        assert event.agent_type == "coding"


class TestArtifactEvent:
    """Test ArtifactEvent model."""

    def test_create_artifact_event(self):
        """Test creating an artifact event."""
        event = ArtifactEvent(
            type=EventType.ARTIFACT_CREATED,
            session_id="session-123",
            artifact_path="src/main.py",
            artifact_type="text/x-python",
        )

        assert event.type == EventType.ARTIFACT_CREATED
        assert event.artifact_path == "src/main.py"
        assert event.artifact_type == "text/x-python"


class TestMessageEvent:
    """Test MessageEvent model."""

    def test_create_message_event(self):
        """Test creating a message event."""
        event = MessageEvent(
            type=EventType.MESSAGE_RECEIVED,
            session_id="session-123",
            message_id="msg-1",
            role="assistant",
            content="Hello!",
            is_complete=True,
        )

        assert event.type == EventType.MESSAGE_RECEIVED
        assert event.message_id == "msg-1"
        assert event.role == "assistant"
        assert event.content == "Hello!"
        assert event.is_complete is True


class TestErrorEvent:
    """Test ErrorEvent model."""

    def test_create_error_event(self):
        """Test creating an error event."""
        event = ErrorEvent(
            error_message="Connection failed",
            error_code="E001",
            recoverable=False,
        )

        assert event.type == EventType.ERROR
        assert event.error_message == "Connection failed"
        assert event.error_code == "E001"
        assert event.recoverable is False


class TestCreateEvent:
    """Test create_event helper function."""

    def test_create_basic_event(self):
        """Test creating a basic event dict."""
        event = create_event(EventType.CONNECTED)

        assert event["type"] == "connected"
        assert event["session_id"] is None
        assert "timestamp" in event
        assert event["payload"] == {}

    def test_create_event_with_payload(self):
        """Test creating an event with payload."""
        event = create_event(
            EventType.AGENT_MESSAGE,
            session_id="session-123",
            content="Hello!",
            sequence=1,
        )

        assert event["type"] == "agent_message"
        assert event["session_id"] == "session-123"
        assert event["payload"]["content"] == "Hello!"
        assert event["payload"]["sequence"] == 1


class TestConnectionManager:
    """Test ConnectionManager class."""

    @pytest.fixture
    def manager(self):
        """Create a fresh connection manager for each test."""
        return ConnectionManager()

    @pytest.mark.asyncio
    async def test_connect(self, manager):
        """Test client connection."""
        await manager.connect("sid-1", "user-1")

        assert manager.connected_clients == 1
        info = manager.get_client_info("sid-1")
        assert info is not None
        assert info.sid == "sid-1"
        assert info.user_id == "user-1"

    @pytest.mark.asyncio
    async def test_disconnect(self, manager):
        """Test client disconnection."""
        await manager.connect("sid-1", "user-1")
        await manager.disconnect("sid-1")

        assert manager.connected_clients == 0
        assert manager.get_client_info("sid-1") is None

    @pytest.mark.asyncio
    async def test_subscribe_to_session(self, manager):
        """Test subscribing to a session."""
        await manager.connect("sid-1")
        result = await manager.subscribe_to_session("sid-1", "session-123")

        assert result is True
        subscribers = manager.get_session_subscribers("session-123")
        assert "sid-1" in subscribers

    @pytest.mark.asyncio
    async def test_subscribe_unknown_client(self, manager):
        """Test subscribing with unknown client."""
        result = await manager.subscribe_to_session("unknown-sid", "session-123")

        assert result is False

    @pytest.mark.asyncio
    async def test_unsubscribe_from_session(self, manager):
        """Test unsubscribing from a session."""
        await manager.connect("sid-1")
        await manager.subscribe_to_session("sid-1", "session-123")
        result = await manager.unsubscribe_from_session("sid-1", "session-123")

        assert result is True
        subscribers = manager.get_session_subscribers("session-123")
        assert "sid-1" not in subscribers

    @pytest.mark.asyncio
    async def test_disconnect_removes_subscriptions(self, manager):
        """Test that disconnect removes all subscriptions."""
        await manager.connect("sid-1")
        await manager.subscribe_to_session("sid-1", "session-1")
        await manager.subscribe_to_session("sid-1", "session-2")

        await manager.disconnect("sid-1")

        assert manager.get_session_subscribers("session-1") == set()
        assert manager.get_session_subscribers("session-2") == set()

    @pytest.mark.asyncio
    async def test_multiple_clients_same_session(self, manager):
        """Test multiple clients subscribing to same session."""
        await manager.connect("sid-1")
        await manager.connect("sid-2")

        await manager.subscribe_to_session("sid-1", "session-123")
        await manager.subscribe_to_session("sid-2", "session-123")

        subscribers = manager.get_session_subscribers("session-123")
        assert len(subscribers) == 2
        assert "sid-1" in subscribers
        assert "sid-2" in subscribers

    @pytest.mark.asyncio
    async def test_active_sessions_count(self, manager):
        """Test active sessions count."""
        await manager.connect("sid-1")
        await manager.connect("sid-2")

        await manager.subscribe_to_session("sid-1", "session-1")
        await manager.subscribe_to_session("sid-2", "session-2")

        assert manager.active_sessions == 2

    @pytest.mark.asyncio
    async def test_get_session_subscribers_empty(self, manager):
        """Test getting subscribers for unknown session."""
        subscribers = manager.get_session_subscribers("unknown-session")
        assert subscribers == set()


class TestClientInfo:
    """Test ClientInfo dataclass."""

    def test_create_client_info(self):
        """Test creating ClientInfo."""
        info = ClientInfo(sid="sid-1", user_id="user-1")

        assert info.sid == "sid-1"
        assert info.user_id == "user-1"
        assert info.subscribed_sessions == set()
        assert info.connected_at == 0.0

    def test_client_info_defaults(self):
        """Test ClientInfo defaults."""
        info = ClientInfo(sid="sid-1")

        assert info.user_id is None
        assert info.subscribed_sessions == set()


class TestSessionEmitter:
    """Test SessionEmitter class."""

    @pytest.fixture
    def emitter(self):
        """Create session emitter for testing."""
        from src.web_backend.websocket.session_emitter import SessionEmitter
        return SessionEmitter("session-123")

    @pytest.mark.asyncio
    async def test_emit_event_agent_message(self, emitter):
        """Test emitting agent message event."""
        with patch("src.web_backend.websocket.server.emit_message") as mock_emit:
            mock_emit.return_value = None

            await emitter.emit_event({
                "type": "agent_message",
                "content": "Hello!",
                "sequence": 1,
            })

            mock_emit.assert_called_once()
            call_args = mock_emit.call_args
            assert call_args[0][0] == "session-123"
            assert call_args[0][1]["content"] == "Hello!"

    @pytest.mark.asyncio
    async def test_emit_event_tool_call(self, emitter):
        """Test emitting tool call event."""
        with patch("src.web_backend.websocket.server.emit_agent_event") as mock_emit:
            mock_emit.return_value = None

            await emitter.emit_event({
                "type": "tool_call",
                "tool_name": "read_file",
                "arguments": {"path": "test.py"},
            })

            mock_emit.assert_called_once()

    @pytest.mark.asyncio
    async def test_emit_event_unknown_type(self, emitter):
        """Test emitting unknown event type."""
        with patch("src.web_backend.websocket.server.emit_to_session") as mock_emit:
            mock_emit.return_value = None

            await emitter.emit_event({
                "type": "custom_event",
                "data": "test",
            })

            mock_emit.assert_called_once()


class TestStreamingMessageEmitter:
    """Test StreamingMessageEmitter class."""

    @pytest.fixture
    def streaming_emitter(self):
        """Create streaming emitter for testing."""
        from src.web_backend.websocket.session_emitter import StreamingMessageEmitter
        return StreamingMessageEmitter("session-123", "msg-1")

    @pytest.mark.asyncio
    async def test_append_content(self, streaming_emitter):
        """Test appending content to stream."""
        with patch("src.web_backend.websocket.server.emit_to_session") as mock_emit:
            mock_emit.return_value = None

            # Append small chunks (below threshold)
            await streaming_emitter.append("Hello")

            assert streaming_emitter.content == "Hello"
            assert not streaming_emitter.is_complete

    @pytest.mark.asyncio
    async def test_complete_stream(self, streaming_emitter):
        """Test completing stream."""
        with patch("src.web_backend.websocket.server.emit_to_session") as mock_emit:
            mock_emit.return_value = None
            with patch("src.web_backend.websocket.server.emit_message") as mock_msg:
                mock_msg.return_value = None

                await streaming_emitter.append("Hello, world!")
                await streaming_emitter.complete()

                assert streaming_emitter.is_complete
                mock_msg.assert_called_once()


class TestWorkflowEmitters:
    """Test workflow event emitters."""

    @pytest.mark.asyncio
    async def test_emit_workflow_phase_started(self):
        """Test emitting phase started event."""
        from src.web_backend.websocket.session_emitter import emit_workflow_phase_started

        with patch("src.web_backend.websocket.server.emit_to_session") as mock_emit:
            mock_emit.return_value = None

            await emit_workflow_phase_started("session-123", "phase-1", "Script Generation")

            mock_emit.assert_called_once()
            args = mock_emit.call_args[0]
            assert args[0] == "session-123"
            assert args[1] == "workflow_update"

    @pytest.mark.asyncio
    async def test_emit_workflow_phase_approved(self):
        """Test emitting phase approved event."""
        from src.web_backend.websocket.session_emitter import emit_workflow_phase_approved

        with patch("src.web_backend.websocket.server.emit_to_session") as mock_emit:
            mock_emit.return_value = None

            await emit_workflow_phase_approved("session-123", "phase-1", "phase-2")

            mock_emit.assert_called_once()

    @pytest.mark.asyncio
    async def test_emit_session_status_change(self):
        """Test emitting session status change event."""
        from src.web_backend.websocket.session_emitter import emit_session_status_change

        with patch("src.web_backend.websocket.server.emit_to_session") as mock_emit:
            mock_emit.return_value = None

            await emit_session_status_change("session-123", "running")

            mock_emit.assert_called_once()
            args = mock_emit.call_args[0]
            assert args[0] == "session-123"
            assert args[1] == "session_update"
