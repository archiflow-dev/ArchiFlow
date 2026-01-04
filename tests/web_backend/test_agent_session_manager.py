"""
Tests for AgentSessionManager.
"""

import pytest
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from dataclasses import dataclass

from src.web_backend.services.agent_session_manager import (
    AgentSessionManager,
    get_agent_session_manager,
)
from src.web_backend.services.agent_runner import (
    WebAgentRunner,
    AgentRunnerPool,
    AgentExecutionError,
)
from src.web_backend.services.web_agent_factory import WebAgentFactory
from src.web_backend.services.web_context import SandboxMode
from src.web_backend.services.workspace_manager import WorkspaceManager
from src.web_backend.services.storage_manager import StorageManager, StorageLimits


@dataclass
class MockSession:
    """Mock session for testing."""
    id: str = "test_session"
    agent_type: str = "simple"
    user_id: str = "test_user"
    user_prompt: str = "Hello, agent!"
    workspace_path: str = None
    status: str = "created"
    messages: list = None
    created_at: object = None
    updated_at: object = None

    def __post_init__(self):
        if self.messages is None:
            self.messages = []
        if self.created_at is None:
            from datetime import datetime, timezone
            self.created_at = datetime.now(timezone.utc)
        if self.updated_at is None:
            from datetime import datetime, timezone
            self.updated_at = datetime.now(timezone.utc)

    def to_dict(self):
        return {
            "id": self.id,
            "agent_type": self.agent_type,
            "user_id": self.user_id,
            "user_prompt": self.user_prompt,
            "workspace_path": self.workspace_path,
            "status": self.status,
        }


class MockSessionService:
    """Mock session service for testing."""

    def __init__(self):
        self.sessions = {}

    async def create(self, agent_type, user_prompt, user_id="default"):
        session = MockSession(
            id=f"session_{len(self.sessions)}",
            agent_type=agent_type,
            user_prompt=user_prompt,
            user_id=user_id,
        )
        self.sessions[session.id] = session
        return session

    async def get(self, session_id):
        return self.sessions.get(session_id)

    async def list(self, user_id=None, status=None, agent_type=None, page=1, page_size=20):
        sessions = list(self.sessions.values())
        if user_id:
            sessions = [s for s in sessions if s.user_id == user_id]
        return sessions, len(sessions)

    async def update_status(self, session_id, status):
        session = self.sessions.get(session_id)
        if session:
            session.status = status.value if hasattr(status, 'value') else status
        return session

    async def delete(self, session_id):
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False


class TestAgentSessionManager:
    """Tests for AgentSessionManager class."""

    @pytest.fixture
    def temp_base(self):
        """Create a temporary directory for workspaces."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def workspace_manager(self, temp_base):
        """Create a WorkspaceManager."""
        return WorkspaceManager(base_path=temp_base)

    @pytest.fixture
    def storage_manager(self, workspace_manager):
        """Create a StorageManager."""
        limits = StorageLimits(
            max_workspace_size_mb=100,
            max_file_size_mb=10,
            max_sessions_per_user=5,
        )
        return StorageManager(
            workspace_manager=workspace_manager,
            limits=limits,
        )

    @pytest.fixture
    def factory(self, workspace_manager, storage_manager):
        """Create a WebAgentFactory."""
        return WebAgentFactory(
            workspace_manager=workspace_manager,
            storage_manager=storage_manager,
            sandbox_mode=SandboxMode.STRICT,
        )

    @pytest.fixture
    def runner_pool(self):
        """Create an AgentRunnerPool."""
        return AgentRunnerPool(max_runners=10)

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = AsyncMock()
        db.commit = AsyncMock()
        return db

    @pytest.fixture
    def manager(self, mock_db, factory, runner_pool):
        """Create an AgentSessionManager in direct mode (for tests)."""
        manager = AgentSessionManager(
            db=mock_db,
            factory=factory,
            runner_pool=runner_pool,
            use_broker=False,  # Use direct mode for tests
        )
        # Replace session service with mock
        manager.session_service = MockSessionService()
        return manager

    @pytest.mark.asyncio
    async def test_create_session(self, manager):
        """Test creating a session."""
        session = await manager.create_session(
            agent_type="simple",
            user_id="test_user",
            user_prompt="Hello",
        )

        assert session is not None
        assert session.agent_type == "simple"
        assert session.user_id == "test_user"
        assert session.workspace_path is not None

    @pytest.mark.asyncio
    async def test_create_session_creates_workspace(self, manager):
        """Test that create_session creates a workspace."""
        session = await manager.create_session(
            agent_type="simple",
            user_id="test_user",
            user_prompt="Hello",
        )

        workspace_path = Path(session.workspace_path)
        assert workspace_path.exists()

    @pytest.mark.asyncio
    async def test_create_session_checks_limit(self, manager, storage_manager):
        """Test that create_session checks session limit."""
        # Create max sessions
        for i in range(5):
            await manager.create_session(
                agent_type="simple",
                user_id="test_user",
                user_prompt=f"Hello {i}",
            )

        # Next one should fail
        with pytest.raises(AgentExecutionError, match="Maximum sessions"):
            await manager.create_session(
                agent_type="simple",
                user_id="test_user",
                user_prompt="Too many",
            )

    @pytest.mark.asyncio
    async def test_get_session(self, manager):
        """Test getting a session."""
        created = await manager.create_session(
            agent_type="simple",
            user_id="test_user",
            user_prompt="Hello",
        )

        retrieved = await manager.get_session(created.id)
        assert retrieved is created

    @pytest.mark.asyncio
    async def test_start_session(self, manager):
        """Test starting a session."""
        session = await manager.create_session(
            agent_type="simple",
            user_id="test_user",
            user_prompt="Hello",
        )

        with patch.object(manager.factory, 'create_agent', new_callable=AsyncMock) as mock_create:
            mock_agent = Mock()
            mock_agent.step = AsyncMock(return_value=Mock(content="Hi"))
            mock_agent.tools = []
            mock_create.return_value = mock_agent

            runner = await manager.start_session(session.id)

            assert runner is not None
            assert runner.is_running

    @pytest.mark.asyncio
    async def test_start_session_not_found(self, manager):
        """Test starting a nonexistent session."""
        with pytest.raises(AgentExecutionError, match="not found"):
            await manager.start_session("nonexistent")

    @pytest.mark.asyncio
    async def test_start_session_already_running(self, manager):
        """Test starting an already running session."""
        session = await manager.create_session(
            agent_type="simple",
            user_id="test_user",
            user_prompt="Hello",
        )

        with patch.object(manager.factory, 'create_agent', new_callable=AsyncMock) as mock_create:
            mock_agent = Mock()
            mock_agent.step = AsyncMock(return_value=Mock(content="Hi"))
            mock_agent.tools = []
            mock_create.return_value = mock_agent

            await manager.start_session(session.id)

            with pytest.raises(AgentExecutionError, match="already running"):
                await manager.start_session(session.id)

    @pytest.mark.asyncio
    async def test_get_or_create_runner_existing(self, manager):
        """Test getting an existing runner."""
        session = await manager.create_session(
            agent_type="simple",
            user_id="test_user",
            user_prompt="Hello",
        )

        with patch.object(manager.factory, 'create_agent', new_callable=AsyncMock) as mock_create:
            mock_agent = Mock()
            mock_agent.step = AsyncMock(return_value=Mock(content="Hi"))
            mock_agent.tools = []
            mock_create.return_value = mock_agent

            # Start session first
            runner1 = await manager.start_session(session.id)

            # Get or create should return same runner
            runner2 = await manager.get_or_create_runner(session.id)

            assert runner2 is runner1

    @pytest.mark.asyncio
    async def test_get_or_create_runner_new(self, manager):
        """Test creating a new runner for stopped session."""
        session = await manager.create_session(
            agent_type="simple",
            user_id="test_user",
            user_prompt="Hello",
        )

        runner = await manager.get_or_create_runner(session.id)

        assert runner is not None
        assert not runner.is_running  # Not started yet

    @pytest.mark.asyncio
    async def test_send_message(self, manager):
        """Test sending a message to running agent."""
        session = await manager.create_session(
            agent_type="simple",
            user_id="test_user",
            user_prompt="Hello",
        )

        with patch.object(manager.factory, 'create_agent', new_callable=AsyncMock) as mock_create:
            mock_agent = Mock()
            mock_agent.step = AsyncMock(return_value=Mock(content="Hi"))
            mock_agent.tools = []
            mock_create.return_value = mock_agent

            await manager.start_session(session.id)
            await manager.send_message(session.id, "Follow up")

            # Agent step should be called twice (initial + follow up)
            assert mock_agent.step.call_count == 2

    @pytest.mark.asyncio
    async def test_send_message_not_active(self, manager):
        """Test sending message to inactive session."""
        with pytest.raises(AgentExecutionError, match="not active"):
            await manager.send_message("nonexistent", "Hello")

    @pytest.mark.asyncio
    async def test_pause_session(self, manager):
        """Test pausing a session."""
        session = await manager.create_session(
            agent_type="simple",
            user_id="test_user",
            user_prompt="Hello",
        )

        with patch.object(manager.factory, 'create_agent', new_callable=AsyncMock) as mock_create:
            mock_agent = Mock()
            mock_agent.step = AsyncMock(return_value=Mock(content="Hi"))
            mock_agent.tools = []
            mock_create.return_value = mock_agent

            await manager.start_session(session.id)
            await manager.pause_session(session.id)

            runner = await manager.runner_pool.get(session.id)
            assert runner.is_paused

    @pytest.mark.asyncio
    async def test_resume_session(self, manager):
        """Test resuming a paused session."""
        session = await manager.create_session(
            agent_type="simple",
            user_id="test_user",
            user_prompt="Hello",
        )

        with patch.object(manager.factory, 'create_agent', new_callable=AsyncMock) as mock_create:
            mock_agent = Mock()
            mock_agent.step = AsyncMock(return_value=Mock(content="Hi"))
            mock_agent.tools = []
            mock_create.return_value = mock_agent

            await manager.start_session(session.id)
            await manager.pause_session(session.id)
            await manager.resume_session(session.id)

            runner = await manager.runner_pool.get(session.id)
            assert not runner.is_paused

    @pytest.mark.asyncio
    async def test_stop_session(self, manager):
        """Test stopping a session."""
        session = await manager.create_session(
            agent_type="simple",
            user_id="test_user",
            user_prompt="Hello",
        )

        with patch.object(manager.factory, 'create_agent', new_callable=AsyncMock) as mock_create:
            mock_agent = Mock()
            mock_agent.step = AsyncMock(return_value=Mock(content="Hi"))
            mock_agent.tools = []
            mock_create.return_value = mock_agent

            await manager.start_session(session.id)
            await manager.stop_session(session.id)

            runner = await manager.runner_pool.get(session.id)
            assert runner is None

    @pytest.mark.asyncio
    async def test_delete_session(self, manager):
        """Test deleting a session."""
        session = await manager.create_session(
            agent_type="simple",
            user_id="test_user",
            user_prompt="Hello",
        )

        result = await manager.delete_session(session.id)

        assert result is True
        assert await manager.get_session(session.id) is None

    @pytest.mark.asyncio
    async def test_delete_session_removes_workspace(self, manager):
        """Test that delete_session removes workspace."""
        session = await manager.create_session(
            agent_type="simple",
            user_id="test_user",
            user_prompt="Hello",
        )

        workspace_path = Path(session.workspace_path)
        assert workspace_path.exists()

        await manager.delete_session(session.id, delete_workspace=True)

        assert not workspace_path.exists()

    @pytest.mark.asyncio
    async def test_get_session_status(self, manager):
        """Test getting session status."""
        session = await manager.create_session(
            agent_type="simple",
            user_id="test_user",
            user_prompt="Hello",
        )

        status = await manager.get_session_status(session.id)

        assert status["session_id"] == session.id
        assert status["agent_type"] == "simple"
        assert status["is_running"] is False

    @pytest.mark.asyncio
    async def test_get_session_status_when_running(self, manager):
        """Test getting session status when running."""
        session = await manager.create_session(
            agent_type="simple",
            user_id="test_user",
            user_prompt="Hello",
        )

        with patch.object(manager.factory, 'create_agent', new_callable=AsyncMock) as mock_create:
            mock_agent = Mock()
            mock_agent.step = AsyncMock(return_value=Mock(content="Hi"))
            mock_agent.tools = []
            mock_agent.history = Mock(messages=[])
            mock_create.return_value = mock_agent

            await manager.start_session(session.id)

            status = await manager.get_session_status(session.id)

            assert status["is_running"] is True
            assert "execution_stats" in status

    @pytest.mark.asyncio
    async def test_list_user_sessions(self, manager):
        """Test listing user sessions."""
        # Create sessions for different users
        await manager.create_session(
            agent_type="simple",
            user_id="user1",
            user_prompt="Hello 1",
        )
        await manager.create_session(
            agent_type="coding",
            user_id="user1",
            user_prompt="Hello 2",
        )
        await manager.create_session(
            agent_type="simple",
            user_id="user2",
            user_prompt="Hello 3",
        )

        sessions = await manager.list_user_sessions("user1")

        assert len(sessions) == 2
        assert all(s["user_id"] == "user1" for s in sessions)

    @pytest.mark.asyncio
    async def test_get_session_history(self, manager):
        """Test getting session history."""
        session = await manager.create_session(
            agent_type="simple",
            user_id="test_user",
            user_prompt="Hello",
        )

        # Add mock messages
        session.messages = [
            Mock(to_dict=lambda: {"id": "1", "content": "Hello", "role": "user"}),
            Mock(to_dict=lambda: {"id": "2", "content": "Hi!", "role": "assistant"}),
        ]

        history = await manager.get_session_history(session.id)

        assert len(history) == 2
