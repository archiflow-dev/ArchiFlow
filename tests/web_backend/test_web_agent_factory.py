"""
Tests for WebAgentFactory.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

from src.web_backend.services.web_agent_factory import (
    WebAgentFactory,
    init_web_agent_factory,
    get_web_agent_factory,
)
from src.web_backend.services.web_context import WebExecutionContext, SandboxMode
from src.web_backend.services.workspace_manager import WorkspaceManager
from src.web_backend.services.storage_manager import StorageManager, StorageLimits
from src.web_backend.services.audit_logger import AuditLogger
from src.web_backend.services.sandboxed_tool import SandboxedToolkit


class TestWebAgentFactory:
    """Tests for WebAgentFactory class."""

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
        )
        return StorageManager(
            workspace_manager=workspace_manager,
            limits=limits,
        )

    @pytest.fixture
    def audit_logger(self, temp_base):
        """Create an AuditLogger."""
        return AuditLogger(base_path=Path(temp_base))

    @pytest.fixture
    def factory(self, workspace_manager, storage_manager, audit_logger):
        """Create a WebAgentFactory."""
        return WebAgentFactory(
            workspace_manager=workspace_manager,
            storage_manager=storage_manager,
            audit_logger=audit_logger,
            sandbox_mode=SandboxMode.STRICT,
        )

    def test_factory_initialization(self, factory, workspace_manager):
        """Test factory initialization."""
        assert factory.workspace_manager is workspace_manager
        assert factory.sandbox_mode == SandboxMode.STRICT

    def test_create_execution_context(self, factory):
        """Test creating execution context."""
        context = factory.create_execution_context(
            session_id="test_session",
            user_id="test_user",
        )

        assert isinstance(context, WebExecutionContext)
        assert context.session_id == "test_session"
        assert context.user_id == "test_user"
        assert context.sandbox_mode == SandboxMode.STRICT
        assert context.workspace_path is not None
        assert context.workspace_path.exists()

    def test_create_execution_context_creates_workspace(self, factory):
        """Test that context creation creates workspace."""
        context = factory.create_execution_context(
            session_id="new_session",
            user_id="new_user",
        )

        assert context.workspace_path.exists()
        assert (context.workspace_path / ".archiflow").exists()

    def test_create_execution_context_custom_options(self, factory):
        """Test context with custom options."""
        context = factory.create_execution_context(
            session_id="test",
            user_id="user",
            timeout=120,
            max_memory_mb=1024,
            allowed_network=False,
        )

        assert context.timeout == 120
        assert context.max_memory_mb == 1024
        assert context.allowed_network is False

    def test_create_execution_context_bash_override(self, factory):
        """Test that bash tool has working_directory override."""
        context = factory.create_execution_context(
            session_id="test",
            user_id="user",
        )

        assert "bash" in context.tool_overrides
        assert "working_directory" in context.tool_overrides["bash"]
        assert context.tool_overrides["bash"]["working_directory"] == str(context.workspace_path)

    def test_wrap_tools(self, factory):
        """Test wrapping tools."""
        # Create mock tools
        mock_tool1 = Mock()
        mock_tool1.name = "read"
        mock_tool2 = Mock()
        mock_tool2.name = "write"

        context = factory.create_execution_context(
            session_id="test",
            user_id="user",
        )

        toolkit = factory.wrap_tools([mock_tool1, mock_tool2], context)

        assert isinstance(toolkit, SandboxedToolkit)
        assert len(toolkit.list_tools()) == 2

    def test_get_agent_tools(self, factory):
        """Test getting tools for agent types."""
        coding_tools = factory.get_agent_tools("coding")
        assert "read" in coding_tools
        assert "write" in coding_tools
        assert "bash" in coding_tools

        comic_tools = factory.get_agent_tools("comic")
        assert "read" in comic_tools
        assert "generate_image" in comic_tools

        unknown_tools = factory.get_agent_tools("unknown")
        assert "read" in unknown_tools  # Default tools

    def test_factory_with_permissive_mode(self, workspace_manager):
        """Test factory with permissive sandbox mode."""
        factory = WebAgentFactory(
            workspace_manager=workspace_manager,
            sandbox_mode=SandboxMode.PERMISSIVE,
        )

        context = factory.create_execution_context(
            session_id="test",
            user_id="user",
        )

        assert context.sandbox_mode == SandboxMode.PERMISSIVE

    def test_factory_with_disabled_mode(self, workspace_manager):
        """Test factory with disabled sandbox mode."""
        factory = WebAgentFactory(
            workspace_manager=workspace_manager,
            sandbox_mode=SandboxMode.DISABLED,
        )

        context = factory.create_execution_context(
            session_id="test",
            user_id="user",
        )

        assert context.sandbox_mode == SandboxMode.DISABLED


class TestGlobalFactory:
    """Tests for global factory instance."""

    def test_init_and_get_factory(self):
        """Test initializing and getting global factory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace_manager = WorkspaceManager(base_path=tmpdir)

            factory = init_web_agent_factory(
                workspace_manager=workspace_manager,
                sandbox_mode=SandboxMode.STRICT,
            )

            retrieved = get_web_agent_factory()
            assert retrieved is factory

    def test_get_factory_without_init_raises(self):
        """Test that getting factory without init raises error."""
        # Reset global instance
        import src.web_backend.services.web_agent_factory as factory_module
        factory_module._factory_instance = None

        with pytest.raises(RuntimeError, match="not initialized"):
            get_web_agent_factory()


class TestWebAgentFactoryCreateAgent:
    """Tests for create_agent method."""

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
    async def test_create_agent_creates_workspace(self, factory):
        """Test that create_agent creates workspace."""
        with patch('agent_cli.agents.factory.create_agent') as mock_create:
            # Mock agent
            mock_agent = Mock()
            mock_agent.tools = []
            mock_create.return_value = mock_agent

            with patch('agent_cli.agents.llm_provider_factory.create_llm_provider'):
                agent = await factory.create_agent(
                    agent_type="simple",
                    session_id="test_session",
                    user_id="test_user",
                )

            # Verify workspace was created
            workspace_path = factory.workspace_manager.get_workspace_path(
                "test_user", "test_session"
            )
            assert workspace_path.exists()

    @pytest.mark.asyncio
    async def test_create_agent_sets_context(self, factory):
        """Test that create_agent sets web context on agent."""
        with patch('agent_cli.agents.factory.create_agent') as mock_create:
            mock_agent = Mock()
            mock_agent.tools = []
            mock_create.return_value = mock_agent

            with patch('agent_cli.agents.llm_provider_factory.create_llm_provider'):
                agent = await factory.create_agent(
                    agent_type="simple",
                    session_id="test_session",
                    user_id="test_user",
                )

            assert hasattr(agent, '_web_context')
            assert isinstance(agent._web_context, WebExecutionContext)

    @pytest.mark.asyncio
    async def test_create_agent_wraps_tools(self, factory):
        """Test that create_agent wraps tools with sandbox."""
        with patch('agent_cli.agents.factory.create_agent') as mock_create:
            # Mock agent with tools
            mock_tool = Mock()
            mock_tool.name = "read"

            mock_agent = Mock()
            mock_agent.tools = [mock_tool]
            mock_create.return_value = mock_agent

            with patch('agent_cli.agents.llm_provider_factory.create_llm_provider'):
                agent = await factory.create_agent(
                    agent_type="coding",
                    session_id="test_session",
                    user_id="test_user",
                )

            # Original tools should be preserved
            assert hasattr(agent, '_original_tools')
            assert len(agent._original_tools) == 1

            # Tools should be wrapped
            assert len(agent.tools) == 1

    @pytest.mark.asyncio
    async def test_create_agent_logs_to_audit(self, temp_base):
        """Test that create_agent logs to audit logger."""
        workspace_manager = WorkspaceManager(base_path=temp_base)
        audit_logger = Mock(spec=AuditLogger)

        factory = WebAgentFactory(
            workspace_manager=workspace_manager,
            audit_logger=audit_logger,
            sandbox_mode=SandboxMode.STRICT,
        )

        with patch('agent_cli.agents.factory.create_agent') as mock_create:
            mock_agent = Mock()
            mock_agent.tools = []
            mock_create.return_value = mock_agent

            with patch('agent_cli.agents.llm_provider_factory.create_llm_provider'):
                await factory.create_agent(
                    agent_type="simple",
                    session_id="test_session",
                    user_id="test_user",
                )

        # Verify audit log was called
        audit_logger.log_session_event.assert_called_once()
        call_args = audit_logger.log_session_event.call_args
        assert call_args.kwargs["session_id"] == "test_session"
        assert call_args.kwargs["user_id"] == "test_user"
        assert call_args.kwargs["event_type"] == "agent_created"
