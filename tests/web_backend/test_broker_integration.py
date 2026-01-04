"""
Integration tests for broker-based agent execution.

Tests the full message flow from WebAgentRunner through WebSessionBroker
to AgentController and back.
"""

import pytest
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from dataclasses import dataclass
from typing import List, Dict, Any

from src.web_backend.services.agent_runner import (
    WebAgentRunner,
    AgentExecutionError,
)
from src.web_backend.services.web_session_broker import (
    WebSessionBroker,
    WebSessionBrokerError,
)
from src.web_backend.services.web_agent_factory import WebAgentFactory
from src.web_backend.services.web_context import SandboxMode
from src.web_backend.services.workspace_manager import WorkspaceManager


@dataclass
class MockSession:
    """Mock session for testing."""
    id: str = "test_session"
    agent_type: str = "simple"
    user_id: str = "test_user"
    user_prompt: str = "Hello, agent!"
    workspace_path: str = "/tmp/workspace"


class MockAgent:
    """Mock agent that simulates real agent behavior."""

    def __init__(self, responses: List[str] = None):
        self.responses = responses or ["Default response"]
        self.response_index = 0
        self.received_messages = []
        self.tool_registry = Mock()
        self.tool_registry.get = Mock(return_value=None)
        self.history = Mock(messages=[])
        self.llm = Mock()
        self._web_context = None

    def step(self, message):
        """Simulate agent step."""
        self.received_messages.append(message)

        # Get next response
        if self.response_index < len(self.responses):
            response_content = self.responses[self.response_index]
            self.response_index += 1
        else:
            response_content = "No more responses"

        # Create mock response
        from agent_framework.messages.types import LLMRespondMessage
        return LLMRespondMessage(
            session_id=message.session_id if hasattr(message, 'session_id') else "test",
            sequence=self.response_index,
            content=response_content,
        )


class TestWebAgentRunnerBrokerMode:
    """Tests for WebAgentRunner in broker mode."""

    @pytest.fixture
    def temp_base(self):
        """Create a temporary directory for workspaces."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def mock_session(self):
        """Create a mock session."""
        return MockSession()

    @pytest.fixture
    def factory(self, temp_base):
        """Create a WebAgentFactory."""
        workspace_manager = WorkspaceManager(base_path=temp_base)
        return WebAgentFactory(
            workspace_manager=workspace_manager,
            sandbox_mode=SandboxMode.STRICT,
        )

    @pytest.fixture
    def runner(self, mock_session, factory):
        """Create a WebAgentRunner in broker mode."""
        return WebAgentRunner(
            session=mock_session,
            factory=factory,
            use_broker=True,  # Force broker mode
        )

    @pytest.mark.asyncio
    async def test_runner_starts_in_broker_mode(self, runner, factory):
        """Test that runner starts in broker mode."""
        with patch.object(factory, 'create_agent', new_callable=AsyncMock) as mock_create:
            mock_agent = MockAgent()
            mock_create.return_value = mock_agent

            await runner.start("Hello")

            assert runner.is_running
            assert runner._use_broker is True
            assert runner._session_broker is not None
            assert runner._session_broker.is_started

            await runner.stop()

    @pytest.mark.asyncio
    async def test_runner_stop_cleans_up_broker(self, runner, factory):
        """Test that stop cleans up the session broker."""
        with patch.object(factory, 'create_agent', new_callable=AsyncMock) as mock_create:
            mock_agent = MockAgent()
            mock_create.return_value = mock_agent

            await runner.start("Hello")
            session_broker = runner._session_broker

            await runner.stop()

            assert not runner.is_running
            assert runner._session_broker is None

    @pytest.mark.asyncio
    async def test_runner_sends_via_broker(self, runner, factory):
        """Test that messages are sent through the broker."""
        with patch.object(factory, 'create_agent', new_callable=AsyncMock) as mock_create:
            mock_agent = MockAgent()
            mock_create.return_value = mock_agent

            await runner.start("Initial prompt")

            # Spy on broker.send_message
            original_send = runner._session_broker.send_message
            send_calls = []

            async def mock_send(content):
                send_calls.append(content)
                return await original_send(content)

            runner._session_broker.send_message = mock_send

            await runner.send_message("Follow up")

            assert "Follow up" in send_calls

            await runner.stop()

    @pytest.mark.asyncio
    async def test_runner_execution_stats_include_broker(self, runner, factory):
        """Test that execution stats include broker information."""
        with patch.object(factory, 'create_agent', new_callable=AsyncMock) as mock_create:
            mock_agent = MockAgent()
            mock_create.return_value = mock_agent

            await runner.start("Hello")

            stats = runner.get_execution_stats()

            assert stats["mode"] == "broker"
            assert "broker_stats" in stats
            assert stats["broker_stats"]["session_id"] == runner.session.id

            await runner.stop()


class TestWebAgentRunnerDirectMode:
    """Tests for WebAgentRunner in direct mode."""

    @pytest.fixture
    def temp_base(self):
        """Create a temporary directory for workspaces."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def mock_session(self):
        """Create a mock session."""
        return MockSession()

    @pytest.fixture
    def factory(self, temp_base):
        """Create a WebAgentFactory."""
        workspace_manager = WorkspaceManager(base_path=temp_base)
        return WebAgentFactory(
            workspace_manager=workspace_manager,
            sandbox_mode=SandboxMode.STRICT,
        )

    @pytest.fixture
    def runner(self, mock_session, factory):
        """Create a WebAgentRunner in direct mode."""
        return WebAgentRunner(
            session=mock_session,
            factory=factory,
            use_broker=False,  # Force direct mode
        )

    @pytest.mark.asyncio
    async def test_runner_starts_in_direct_mode(self, runner, factory):
        """Test that runner starts in direct mode."""
        with patch.object(factory, 'create_agent', new_callable=AsyncMock) as mock_create:
            mock_agent = Mock()
            mock_agent.step = AsyncMock(return_value=Mock(content="Response"))
            mock_create.return_value = mock_agent

            await runner.start("Hello")

            assert runner.is_running
            assert runner._use_broker is False
            assert runner._session_broker is None

            await runner.stop()

    @pytest.mark.asyncio
    async def test_runner_calls_agent_directly(self, runner, factory):
        """Test that agent.step is called directly in direct mode."""
        with patch.object(factory, 'create_agent', new_callable=AsyncMock) as mock_create:
            mock_agent = Mock()
            mock_agent.step = AsyncMock(return_value=Mock(content="Response"))
            mock_create.return_value = mock_agent

            await runner.start("Hello")
            await runner.send_message("Follow up")

            # Agent step should be called twice (initial + follow up)
            assert mock_agent.step.call_count == 2

            await runner.stop()

    @pytest.mark.asyncio
    async def test_runner_execution_stats_direct_mode(self, runner, factory):
        """Test that execution stats show direct mode."""
        with patch.object(factory, 'create_agent', new_callable=AsyncMock) as mock_create:
            mock_agent = Mock()
            mock_agent.step = AsyncMock(return_value=Mock(content="Response"))
            mock_agent.history = Mock(messages=[])  # Fix: provide list for len()
            mock_create.return_value = mock_agent

            await runner.start("Hello")

            stats = runner.get_execution_stats()

            assert stats["mode"] == "direct"
            assert "broker_stats" not in stats

            await runner.stop()


class TestMessageCallbackIntegration:
    """Tests for message callback integration."""

    @pytest.fixture
    def temp_base(self):
        """Create a temporary directory for workspaces."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def factory(self, temp_base):
        """Create a WebAgentFactory."""
        workspace_manager = WorkspaceManager(base_path=temp_base)
        return WebAgentFactory(
            workspace_manager=workspace_manager,
            sandbox_mode=SandboxMode.STRICT,
        )

    @pytest.mark.asyncio
    async def test_callback_receives_broker_events(self, factory):
        """Test that callback receives events from broker mode."""
        received_events = []

        async def callback(event):
            received_events.append(event)

        session = MockSession()
        runner = WebAgentRunner(
            session=session,
            factory=factory,
            message_callback=callback,
            use_broker=True,
        )

        with patch.object(factory, 'create_agent', new_callable=AsyncMock) as mock_create:
            mock_agent = MockAgent()
            mock_create.return_value = mock_agent

            await runner.start("Hello")

            # Wait for events to be processed
            await asyncio.sleep(0.1)

            # Should receive agent_started event
            event_types = [e.get("type") for e in received_events]
            assert "agent_started" in event_types

            await runner.stop()

    @pytest.mark.asyncio
    async def test_callback_receives_direct_events(self, factory):
        """Test that callback receives events from direct mode."""
        received_events = []

        async def callback(event):
            received_events.append(event)

        session = MockSession()
        runner = WebAgentRunner(
            session=session,
            factory=factory,
            message_callback=callback,
            use_broker=False,
        )

        with patch.object(factory, 'create_agent', new_callable=AsyncMock) as mock_create:
            mock_agent = Mock()
            mock_agent.step = AsyncMock(return_value=Mock(content="Response"))
            mock_create.return_value = mock_agent

            await runner.start("Hello")

            # Should receive events
            event_types = [e.get("type") for e in received_events]
            assert "agent_started" in event_types
            assert "user_message" in event_types

            await runner.stop()


class TestBrokerToolExecution:
    """Tests for tool execution through broker."""

    @pytest.fixture
    def temp_base(self):
        """Create a temporary directory for workspaces."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.mark.asyncio
    async def test_executor_receives_tool_registry(self, temp_base):
        """Test that RuntimeExecutor receives the agent's tool registry."""
        workspace = Path(temp_base)

        # Create agent with tool registry
        mock_agent = MockAgent()
        mock_tool = Mock()
        mock_tool.name = "test_tool"
        mock_agent.tool_registry = Mock()
        mock_agent.tool_registry.get = Mock(return_value=mock_tool)

        broker = WebSessionBroker(
            session_id="tool_test",
            user_id="test_user",
            agent=mock_agent,
            workspace_path=workspace,
            ws_callback=AsyncMock(),
        )

        await broker.start()

        # Executor should have the tool registry
        assert broker.executor.tool_registry is mock_agent.tool_registry

        await broker.stop()


class TestBrokerErrorHandling:
    """Tests for error handling in broker mode."""

    @pytest.fixture
    def temp_base(self):
        """Create a temporary directory for workspaces."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def factory(self, temp_base):
        """Create a WebAgentFactory."""
        workspace_manager = WorkspaceManager(base_path=temp_base)
        return WebAgentFactory(
            workspace_manager=workspace_manager,
            sandbox_mode=SandboxMode.STRICT,
        )

    @pytest.mark.asyncio
    async def test_broker_start_failure_is_handled(self, factory):
        """Test that broker start failure is handled gracefully."""
        session = MockSession()
        runner = WebAgentRunner(
            session=session,
            factory=factory,
            use_broker=True,
        )

        with patch.object(factory, 'create_agent', new_callable=AsyncMock) as mock_create:
            mock_agent = MockAgent()
            mock_create.return_value = mock_agent

            # Patch WebSessionBroker.start to fail
            with patch.object(
                WebSessionBroker, 'start',
                side_effect=WebSessionBrokerError("Start failed")
            ):
                with pytest.raises(AgentExecutionError, match="Failed to start"):
                    await runner.start("Hello")

            # Runner should not be running
            assert not runner.is_running

    @pytest.mark.asyncio
    async def test_send_message_when_broker_fails(self, factory):
        """Test handling of broker failures during message send."""
        session = MockSession()
        runner = WebAgentRunner(
            session=session,
            factory=factory,
            use_broker=True,
        )

        with patch.object(factory, 'create_agent', new_callable=AsyncMock) as mock_create:
            mock_agent = MockAgent()
            mock_create.return_value = mock_agent

            await runner.start("Hello")

            # Patch send_message to fail
            original_send = runner._session_broker.send_message

            async def failing_send(content):
                raise WebSessionBrokerError("Send failed")

            runner._session_broker.send_message = failing_send

            with pytest.raises(WebSessionBrokerError, match="Send failed"):
                await runner.send_message("This will fail")

            await runner.stop()


class TestModeSelection:
    """Tests for broker/direct mode selection."""

    @pytest.fixture
    def temp_base(self):
        """Create a temporary directory for workspaces."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def factory(self, temp_base):
        """Create a WebAgentFactory."""
        workspace_manager = WorkspaceManager(base_path=temp_base)
        return WebAgentFactory(
            workspace_manager=workspace_manager,
            sandbox_mode=SandboxMode.STRICT,
        )

    def test_explicit_broker_mode(self, factory):
        """Test explicit broker mode selection."""
        session = MockSession()
        runner = WebAgentRunner(
            session=session,
            factory=factory,
            use_broker=True,
        )
        assert runner._use_broker is True

    def test_explicit_direct_mode(self, factory):
        """Test explicit direct mode selection."""
        session = MockSession()
        runner = WebAgentRunner(
            session=session,
            factory=factory,
            use_broker=False,
        )
        assert runner._use_broker is False

    def test_default_mode_from_env(self, factory):
        """Test that default mode comes from environment."""
        session = MockSession()

        # Default is True (broker mode)
        runner = WebAgentRunner(
            session=session,
            factory=factory,
        )

        # Should use the global USE_BROKER_ARCHITECTURE value
        from src.web_backend.services.agent_runner import USE_BROKER_ARCHITECTURE
        assert runner._use_broker == USE_BROKER_ARCHITECTURE
