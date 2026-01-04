"""
Tests for WebAgentRunner and AgentRunnerPool.
"""

import pytest
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from dataclasses import dataclass

from src.web_backend.services.agent_runner import (
    WebAgentRunner,
    AgentRunnerPool,
    AgentExecutionError,
    get_runner_pool,
)
from src.web_backend.services.web_agent_factory import WebAgentFactory
from src.web_backend.services.web_context import WebExecutionContext, SandboxMode
from src.web_backend.services.workspace_manager import WorkspaceManager


@dataclass
class MockSession:
    """Mock session for testing."""
    id: str = "test_session"
    agent_type: str = "simple"
    user_id: str = "test_user"
    user_prompt: str = "Hello, agent!"
    workspace_path: str = "/tmp/workspace"


class TestWebAgentRunner:
    """Tests for WebAgentRunner class."""

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
    def mock_factory(self, temp_base):
        """Create a mock factory."""
        workspace_manager = WorkspaceManager(base_path=temp_base)

        factory = WebAgentFactory(
            workspace_manager=workspace_manager,
            sandbox_mode=SandboxMode.STRICT,
        )

        return factory

    @pytest.fixture
    def runner(self, mock_session, mock_factory):
        """Create a WebAgentRunner in direct mode (for backward compatibility)."""
        return WebAgentRunner(
            session=mock_session,
            factory=mock_factory,
            use_broker=False,  # Use direct mode for existing tests
        )

    def test_runner_initialization(self, runner, mock_session):
        """Test runner initialization."""
        assert runner.session is mock_session
        assert runner.agent is None
        assert not runner.is_running
        assert not runner.is_paused

    @pytest.mark.asyncio
    async def test_start_creates_agent(self, runner, mock_factory):
        """Test that start creates an agent."""
        with patch.object(mock_factory, 'create_agent', new_callable=AsyncMock) as mock_create:
            mock_agent = Mock()
            mock_agent.step = AsyncMock(return_value=Mock(content="Hello!"))
            mock_create.return_value = mock_agent

            await runner.start("Hello")

            mock_create.assert_called_once()
            assert runner.agent is mock_agent
            assert runner.is_running

    @pytest.mark.asyncio
    async def test_start_twice_raises(self, runner, mock_factory):
        """Test that starting twice raises error."""
        with patch.object(mock_factory, 'create_agent', new_callable=AsyncMock) as mock_create:
            mock_agent = Mock()
            mock_agent.step = AsyncMock(return_value=Mock(content="Hello!"))
            mock_create.return_value = mock_agent

            await runner.start("Hello")

            with pytest.raises(AgentExecutionError, match="already running"):
                await runner.start("Hello again")

    @pytest.mark.asyncio
    async def test_send_message_when_running(self, runner, mock_factory):
        """Test sending message to running agent."""
        with patch.object(mock_factory, 'create_agent', new_callable=AsyncMock) as mock_create:
            mock_agent = Mock()
            mock_agent.step = AsyncMock(return_value=Mock(content="Response"))
            mock_create.return_value = mock_agent

            await runner.start("Initial prompt")
            await runner.send_message("Follow up")

            # Agent step should be called twice
            assert mock_agent.step.call_count == 2

    @pytest.mark.asyncio
    async def test_send_message_when_not_running_raises(self, runner):
        """Test that sending message when not running raises error."""
        with pytest.raises(AgentExecutionError, match="not running"):
            await runner.send_message("Hello")

    @pytest.mark.asyncio
    async def test_send_message_when_paused_raises(self, runner, mock_factory):
        """Test that sending message when paused raises error."""
        with patch.object(mock_factory, 'create_agent', new_callable=AsyncMock) as mock_create:
            mock_agent = Mock()
            mock_agent.step = AsyncMock(return_value=Mock(content="Response"))
            mock_create.return_value = mock_agent

            await runner.start("Initial prompt")
            await runner.pause()

            with pytest.raises(AgentExecutionError, match="paused"):
                await runner.send_message("Hello")

    @pytest.mark.asyncio
    async def test_pause_and_resume(self, runner, mock_factory):
        """Test pausing and resuming agent."""
        with patch.object(mock_factory, 'create_agent', new_callable=AsyncMock) as mock_create:
            mock_agent = Mock()
            mock_agent.step = AsyncMock(return_value=Mock(content="Response"))
            mock_create.return_value = mock_agent

            await runner.start("Initial prompt")
            assert runner.is_running
            assert not runner.is_paused

            await runner.pause()
            assert runner.is_paused

            await runner.resume()
            assert not runner.is_paused
            assert runner.is_running

    @pytest.mark.asyncio
    async def test_stop(self, runner, mock_factory):
        """Test stopping agent."""
        with patch.object(mock_factory, 'create_agent', new_callable=AsyncMock) as mock_create:
            mock_agent = Mock()
            mock_agent.step = AsyncMock(return_value=Mock(content="Response"))
            mock_create.return_value = mock_agent

            await runner.start("Initial prompt")
            assert runner.is_running

            await runner.stop()
            assert not runner.is_running

    @pytest.mark.asyncio
    async def test_message_callback(self, runner, mock_factory):
        """Test that message callback is called."""
        callback = AsyncMock()
        runner.message_callback = callback

        with patch.object(mock_factory, 'create_agent', new_callable=AsyncMock) as mock_create:
            mock_agent = Mock()
            mock_agent.step = AsyncMock(return_value=Mock(content="Response"))
            mock_create.return_value = mock_agent

            await runner.start("Hello")

            # Callback should be called for agent_started and user_message events
            assert callback.call_count >= 2

    def test_get_execution_stats(self, runner, mock_session):
        """Test getting execution stats."""
        stats = runner.get_execution_stats()

        assert stats["session_id"] == mock_session.id
        assert stats["agent_type"] == mock_session.agent_type
        assert stats["is_running"] is False
        assert stats["is_paused"] is False


class TestAgentRunnerPool:
    """Tests for AgentRunnerPool class."""

    @pytest.fixture
    def pool(self):
        """Create an AgentRunnerPool."""
        return AgentRunnerPool(max_runners=5)

    @pytest.fixture
    def mock_runner(self):
        """Create a mock runner."""
        runner = Mock()
        runner.session = MockSession()
        runner.is_running = True
        runner.stop = AsyncMock()
        return runner

    @pytest.mark.asyncio
    async def test_add_runner(self, pool, mock_runner):
        """Test adding a runner."""
        await pool.add(mock_runner)
        assert pool.count() == 1

    @pytest.mark.asyncio
    async def test_get_runner(self, pool, mock_runner):
        """Test getting a runner by session ID."""
        await pool.add(mock_runner)

        retrieved = await pool.get(mock_runner.session.id)
        assert retrieved is mock_runner

    @pytest.mark.asyncio
    async def test_get_nonexistent_runner(self, pool):
        """Test getting a runner that doesn't exist."""
        retrieved = await pool.get("nonexistent")
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_remove_runner(self, pool, mock_runner):
        """Test removing a runner."""
        await pool.add(mock_runner)
        assert pool.count() == 1

        removed = await pool.remove(mock_runner.session.id)
        assert removed is mock_runner
        assert pool.count() == 0

    @pytest.mark.asyncio
    async def test_max_runners_limit(self, pool, mock_runner):
        """Test that max runners limit is enforced."""
        # Add max runners
        for i in range(5):
            runner = Mock()
            runner.session = MockSession(id=f"session_{i}")
            await pool.add(runner)

        # Adding one more should raise
        extra_runner = Mock()
        extra_runner.session = MockSession(id="extra")

        with pytest.raises(AgentExecutionError, match="Maximum runners"):
            await pool.add(extra_runner)

    @pytest.mark.asyncio
    async def test_stop_all(self, pool):
        """Test stopping all runners."""
        for i in range(3):
            runner = Mock()
            runner.session = MockSession(id=f"session_{i}")
            runner.stop = AsyncMock()
            await pool.add(runner)

        await pool.stop_all()

        assert pool.count() == 0

    @pytest.mark.asyncio
    async def test_list_active(self, pool):
        """Test listing active session IDs."""
        for i in range(3):
            runner = Mock()
            runner.session = MockSession(id=f"session_{i}")
            await pool.add(runner)

        active = pool.list_active()
        assert len(active) == 3
        assert "session_0" in active
        assert "session_1" in active
        assert "session_2" in active


class TestGlobalRunnerPool:
    """Tests for global runner pool."""

    def test_get_runner_pool(self):
        """Test getting global runner pool."""
        pool = get_runner_pool()
        assert isinstance(pool, AgentRunnerPool)

    def test_get_runner_pool_singleton(self):
        """Test that global runner pool is singleton."""
        pool1 = get_runner_pool()
        pool2 = get_runner_pool()
        assert pool1 is pool2


class TestWebAgentRunnerWithRealFactory:
    """Integration tests with real factory."""

    @pytest.fixture
    def temp_base(self):
        """Create a temporary directory for workspaces."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def factory(self, temp_base):
        """Create a real WebAgentFactory."""
        workspace_manager = WorkspaceManager(base_path=temp_base)
        return WebAgentFactory(
            workspace_manager=workspace_manager,
            sandbox_mode=SandboxMode.STRICT,
        )

    @pytest.mark.asyncio
    async def test_runner_creates_workspace(self, factory):
        """Test that runner creates workspace on start."""
        session = MockSession()
        runner = WebAgentRunner(session=session, factory=factory, use_broker=False)

        with patch('agent_cli.agents.factory.create_agent') as mock_create:
            mock_agent = Mock()
            mock_agent.step = AsyncMock(return_value=Mock(content="Hi"))
            mock_agent.tools = []
            mock_create.return_value = mock_agent

            with patch('agent_cli.agents.llm_provider_factory.create_llm_provider'):
                await runner.start("Hello")

        # Workspace should exist
        workspace = factory.workspace_manager.get_workspace_path(
            session.user_id, session.id
        )
        assert workspace.exists()

    @pytest.mark.asyncio
    async def test_runner_context_is_set(self, factory):
        """Test that runner has context after start."""
        session = MockSession()
        runner = WebAgentRunner(session=session, factory=factory, use_broker=False)

        with patch('agent_cli.agents.factory.create_agent') as mock_create:
            mock_agent = Mock()
            mock_agent.step = AsyncMock(return_value=Mock(content="Hi"))
            mock_agent.tools = []
            mock_agent._web_context = factory.create_execution_context(
                session_id=session.id,
                user_id=session.user_id,
            )
            mock_create.return_value = mock_agent

            with patch('agent_cli.agents.llm_provider_factory.create_llm_provider'):
                await runner.start("Hello")

        assert runner.context is not None
        assert isinstance(runner.context, WebExecutionContext)
