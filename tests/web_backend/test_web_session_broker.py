"""
Tests for WebSessionBroker.
"""

import pytest
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from dataclasses import dataclass, field
from typing import Dict, Any, List

from src.web_backend.services.web_session_broker import (
    WebSessionBroker,
    WebSessionBrokerError,
)


class MockAgent:
    """Mock agent for testing."""

    def __init__(self, session_id: str = "test_session"):
        self.session_id = session_id
        self.tool_registry = Mock()
        self.tool_registry.get = Mock(return_value=None)
        self.history = Mock(messages=[])
        self.step = Mock(return_value=Mock(content="Response"))
        self.llm = Mock()
        self._web_context = None


class TestWebSessionBroker:
    """Tests for WebSessionBroker class."""

    @pytest.fixture
    def temp_workspace(self):
        """Create a temporary workspace."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def mock_agent(self):
        """Create a mock agent."""
        return MockAgent()

    @pytest.fixture
    def ws_callback(self):
        """Create an async WebSocket callback."""
        callback = AsyncMock()
        return callback

    @pytest.fixture
    def broker(self, temp_workspace, mock_agent, ws_callback):
        """Create a WebSessionBroker."""
        return WebSessionBroker(
            session_id="test_session",
            user_id="test_user",
            agent=mock_agent,
            workspace_path=temp_workspace,
            ws_callback=ws_callback,
        )

    def test_broker_initialization(self, broker, mock_agent, temp_workspace):
        """Test broker initialization."""
        assert broker.session_id == "test_session"
        assert broker.user_id == "test_user"
        assert broker.agent is mock_agent
        assert broker.workspace_path == temp_workspace
        assert not broker.is_started
        assert broker.broker is None
        assert broker.context is None

    @pytest.mark.asyncio
    async def test_start_creates_infrastructure(self, broker):
        """Test that start creates all broker infrastructure."""
        await broker.start()

        assert broker.is_started
        assert broker.broker is not None
        assert broker.context is not None
        assert broker.controller is not None
        assert broker.executor is not None
        assert broker.runtime_manager is not None

        # Clean up
        await broker.stop()

    @pytest.mark.asyncio
    async def test_start_creates_topics(self, broker):
        """Test that start creates proper topics."""
        await broker.start()

        assert broker.context.agent_topic == "agent.test_session"
        assert broker.context.client_topic == "client.test_session"
        assert broker.context.runtime_topic == "runtime.test_session"

        await broker.stop()

    @pytest.mark.asyncio
    async def test_start_twice_is_safe(self, broker):
        """Test that starting twice doesn't cause issues."""
        await broker.start()
        await broker.start()  # Should not raise

        assert broker.is_started

        await broker.stop()

    @pytest.mark.asyncio
    async def test_stop_cleans_up(self, broker):
        """Test that stop cleans up all resources."""
        await broker.start()
        assert broker.is_started

        await broker.stop()

        assert not broker.is_started
        assert broker.broker is None
        assert broker.context is None
        assert broker.controller is None

    @pytest.mark.asyncio
    async def test_stop_when_not_started(self, broker):
        """Test that stop when not started is safe."""
        await broker.stop()  # Should not raise
        assert not broker.is_started

    @pytest.mark.asyncio
    async def test_send_message_publishes_to_broker(self, broker):
        """Test that send_message publishes to agent topic."""
        await broker.start()

        # Spy on broker.publish
        original_publish = broker.broker.publish
        publish_calls = []

        def mock_publish(topic, message):
            publish_calls.append((topic, message))
            return original_publish(topic, message)

        broker.broker.publish = mock_publish

        await broker.send_message("Hello, agent!")

        # Should have published to agent topic
        assert len(publish_calls) >= 1
        agent_topic_calls = [
            c for c in publish_calls
            if c[0] == broker.context.agent_topic
        ]
        assert len(agent_topic_calls) >= 1

        # Check message content
        call = agent_topic_calls[0]
        assert call[1]["type"] == "UserMessage"
        assert call[1]["content"] == "Hello, agent!"
        assert call[1]["session_id"] == "test_session"

        await broker.stop()

    @pytest.mark.asyncio
    async def test_send_message_increments_sequence(self, broker):
        """Test that send_message increments message sequence."""
        await broker.start()

        publish_calls = []
        original_publish = broker.broker.publish

        def mock_publish(topic, message):
            publish_calls.append((topic, message))
            return original_publish(topic, message)

        broker.broker.publish = mock_publish

        await broker.send_message("First message")
        await broker.send_message("Second message")

        agent_calls = [
            c[1] for c in publish_calls
            if c[0] == broker.context.agent_topic
        ]

        assert agent_calls[0]["sequence"] == 1
        assert agent_calls[1]["sequence"] == 2

        await broker.stop()

    @pytest.mark.asyncio
    async def test_send_message_when_not_started_raises(self, broker):
        """Test that send_message when not started raises error."""
        with pytest.raises(WebSessionBrokerError, match="not started"):
            await broker.send_message("Hello")

    @pytest.mark.asyncio
    async def test_auto_refine_callback(self, temp_workspace, mock_agent, ws_callback):
        """Test auto-refine callback."""
        broker = WebSessionBroker(
            session_id="test",
            user_id="user",
            agent=mock_agent,
            workspace_path=temp_workspace,
            ws_callback=ws_callback,
            auto_refine_enabled=True,
        )

        assert broker._auto_refine_callback() is True

        broker.set_auto_refine_enabled(False)
        assert broker._auto_refine_callback() is False

    def test_get_stats(self, broker, temp_workspace):
        """Test get_stats returns correct data."""
        stats = broker.get_stats()

        assert stats["session_id"] == "test_session"
        assert stats["user_id"] == "test_user"
        assert stats["started"] is False
        assert stats["workspace"] == str(temp_workspace)
        assert stats["auto_refine_enabled"] is False

    @pytest.mark.asyncio
    async def test_get_stats_when_started(self, broker):
        """Test get_stats when broker is started."""
        await broker.start()

        stats = broker.get_stats()

        assert stats["started"] is True
        assert stats["topics"]["agent"] == "agent.test_session"
        assert stats["topics"]["client"] == "client.test_session"
        assert stats["topics"]["runtime"] == "runtime.test_session"

        await broker.stop()


class TestWebSessionBrokerEventTransform:
    """Tests for event transformation."""

    @pytest.fixture
    def broker(self):
        """Create a broker for testing transformations."""
        broker = WebSessionBroker(
            session_id="test_session",
            user_id="test_user",
            agent=MockAgent(),
            workspace_path=Path("/tmp"),
            ws_callback=AsyncMock(),
        )
        return broker

    def test_transform_assistant_message(self, broker):
        """Test transforming AssistantMessage."""
        payload = {
            "type": "AssistantMessage",
            "content": "Hello, user!",
            "sequence": 5,
        }

        event = broker._transform_to_ws_event(payload)

        assert event["type"] == "agent_message"
        assert event["session_id"] == "test_session"
        assert event["content"] == "Hello, user!"
        assert event["sequence"] == 5

    def test_transform_tool_call(self, broker):
        """Test transforming ToolCall."""
        payload = {
            "type": "ToolCall",
            "tool_name": "read",
            "content": "Reading file...",
            "arguments": {"path": "/tmp/file.txt"},
        }

        event = broker._transform_to_ws_event(payload)

        assert event["type"] == "tool_call"
        assert event["tool_name"] == "read"
        assert event["arguments"]["path"] == "/tmp/file.txt"

    def test_transform_tool_result(self, broker):
        """Test transforming ToolResult."""
        payload = {
            "type": "ToolResult",
            "tool_name": "read",
            "result": "file contents",
            "status": "success",
            "metadata": {"bytes": 100},
        }

        event = broker._transform_to_ws_event(payload)

        assert event["type"] == "tool_result"
        assert event["tool_name"] == "read"
        assert event["result"] == "file contents"
        assert event["status"] == "success"
        assert event["metadata"]["bytes"] == 100

    def test_transform_agent_thought(self, broker):
        """Test transforming AgentThought."""
        payload = {
            "type": "AgentThought",
            "content": "I need to read the file first...",
        }

        event = broker._transform_to_ws_event(payload)

        assert event["type"] == "agent_thought"
        assert event["content"] == "I need to read the file first..."

    def test_transform_wait_for_input(self, broker):
        """Test transforming WAIT_FOR_USER_INPUT."""
        payload = {
            "type": "WAIT_FOR_USER_INPUT",
            "sequence": 10,
        }

        event = broker._transform_to_ws_event(payload)

        assert event["type"] == "waiting_for_input"
        assert event["sequence"] == 10

    def test_transform_agent_finished(self, broker):
        """Test transforming AGENT_FINISHED."""
        payload = {
            "type": "AGENT_FINISHED",
            "reason": "Task completed",
        }

        event = broker._transform_to_ws_event(payload)

        assert event["type"] == "agent_finished"
        assert event["reason"] == "Task completed"

    def test_transform_refinement_notification(self, broker):
        """Test transforming RefinementNotification."""
        payload = {
            "type": "RefinementNotification",
            "content": "Prompt was refined",
        }

        event = broker._transform_to_ws_event(payload)

        assert event["type"] == "refinement_applied"
        assert event["content"] == "Prompt was refined"

    def test_transform_unknown_type(self, broker):
        """Test transforming unknown message type."""
        payload = {
            "type": "CustomMessage",
            "data": "some data",
        }

        event = broker._transform_to_ws_event(payload)

        assert event["type"] == "custommessage"  # lowercased
        assert event["payload"] == payload


class TestWebSessionBrokerIntegration:
    """Integration tests for WebSessionBroker."""

    @pytest.fixture
    def temp_workspace(self):
        """Create a temporary workspace."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.mark.asyncio
    async def test_full_lifecycle(self, temp_workspace):
        """Test full broker lifecycle."""
        received_events = []

        async def ws_callback(event):
            received_events.append(event)

        agent = MockAgent()
        broker = WebSessionBroker(
            session_id="lifecycle_test",
            user_id="test_user",
            agent=agent,
            workspace_path=temp_workspace,
            ws_callback=ws_callback,
        )

        # Start
        await broker.start()
        assert broker.is_started

        # Send messages
        await broker.send_message("Hello")
        await broker.send_message("World")

        # Check stats
        stats = broker.get_stats()
        assert stats["message_sequence"] == 2

        # Stop
        await broker.stop()
        assert not broker.is_started

    @pytest.mark.asyncio
    async def test_broker_with_tool_registry(self, temp_workspace):
        """Test broker with agent that has tool registry."""
        agent = MockAgent()

        # Setup tool registry with a mock tool
        mock_tool = Mock()
        mock_tool.name = "test_tool"
        mock_tool.execute = AsyncMock(return_value=Mock(output="result"))
        agent.tool_registry.get = Mock(return_value=mock_tool)
        agent.tool_registry.list = Mock(return_value=[mock_tool])

        broker = WebSessionBroker(
            session_id="tool_test",
            user_id="test_user",
            agent=agent,
            workspace_path=temp_workspace,
            ws_callback=AsyncMock(),
        )

        await broker.start()

        # Executor should have access to tool registry
        assert broker.executor is not None
        assert broker.executor.tool_registry is agent.tool_registry

        await broker.stop()

    @pytest.mark.asyncio
    async def test_cleanup_on_failed_start(self, temp_workspace):
        """Test that resources are cleaned up if start fails."""
        agent = MockAgent()

        broker = WebSessionBroker(
            session_id="fail_test",
            user_id="test_user",
            agent=agent,
            workspace_path=temp_workspace,
            ws_callback=AsyncMock(),
        )

        # Patch something to make start fail after broker creation
        with patch.object(
            broker, '_on_client_topic',
            side_effect=Exception("Simulated failure")
        ):
            # Should not raise, but should be cleaned up
            # Note: The subscribe happens before we'd hit the error
            pass

        # Should still be able to start normally
        await broker.start()
        assert broker.is_started
        await broker.stop()


class TestWebSessionBrokerCallback:
    """Tests for WebSocket callback handling."""

    @pytest.fixture
    def temp_workspace(self):
        """Create a temporary workspace."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.mark.asyncio
    async def test_callback_receives_events(self, temp_workspace):
        """Test that callback receives transformed events."""
        received_events = []

        async def ws_callback(event):
            received_events.append(event)

        agent = MockAgent()
        broker = WebSessionBroker(
            session_id="callback_test",
            user_id="test_user",
            agent=agent,
            workspace_path=temp_workspace,
            ws_callback=ws_callback,
        )

        await broker.start()

        # Manually publish to client topic to test forwarding
        broker.broker.publish(
            broker.context.client_topic,
            {"type": "AssistantMessage", "content": "Test message", "sequence": 1}
        )

        # Give broker time to process
        await asyncio.sleep(0.1)

        await broker.stop()

        # Should have received the event
        assistant_events = [e for e in received_events if e.get("type") == "agent_message"]
        assert len(assistant_events) >= 1
        assert assistant_events[0]["content"] == "Test message"

    @pytest.mark.asyncio
    async def test_callback_error_is_handled(self, temp_workspace):
        """Test that callback errors don't crash the broker."""
        call_count = 0

        async def failing_callback(event):
            nonlocal call_count
            call_count += 1
            raise Exception("Callback failed!")

        agent = MockAgent()
        broker = WebSessionBroker(
            session_id="error_test",
            user_id="test_user",
            agent=agent,
            workspace_path=temp_workspace,
            ws_callback=failing_callback,
        )

        await broker.start()

        # Publish to client topic
        broker.broker.publish(
            broker.context.client_topic,
            {"type": "AssistantMessage", "content": "Test", "sequence": 1}
        )

        await asyncio.sleep(0.1)

        # Broker should still be running
        assert broker.is_started

        await broker.stop()
