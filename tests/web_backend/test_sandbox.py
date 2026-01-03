"""
Tests for WebExecutionContext and SandboxedToolWrapper.
"""

import pytest
import tempfile
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

from src.web_backend.services.web_context import (
    WebExecutionContext,
    SandboxMode,
)
from src.web_backend.services.sandboxed_tool import (
    SandboxedToolWrapper,
    SandboxedToolkit,
    SandboxViolationError,
)
from src.web_backend.services.workspace_manager import (
    WorkspaceManager,
    WorkspaceSecurityError,
)
from src.web_backend.services.storage_manager import (
    StorageManager,
    StorageLimits,
)
from src.web_backend.services.audit_logger import AuditLogger


class TestWebExecutionContext:
    """Tests for WebExecutionContext class."""

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
        return StorageManager(workspace_manager=workspace_manager)

    def test_create_context(self, workspace_manager):
        """Test creating a web execution context."""
        workspace_manager.create_workspace("user1", "session1")
        workspace_path = workspace_manager.get_workspace_path("user1", "session1")

        context = WebExecutionContext(
            session_id="session1",
            user_id="user1",
            workspace_path=workspace_path,
            workspace_manager=workspace_manager,
        )

        assert context.session_id == "session1"
        assert context.user_id == "user1"
        assert context.sandbox_mode == SandboxMode.STRICT

    def test_create_for_session_factory(self, workspace_manager, storage_manager):
        """Test the factory method for creating context."""
        context = WebExecutionContext.create_for_session(
            session_id="session1",
            user_id="user1",
            workspace_manager=workspace_manager,
            storage_manager=storage_manager,
        )

        assert context.session_id == "session1"
        assert context.workspace_path.exists()
        assert context.working_directory == str(context.workspace_path)

    def test_validate_path_success(self, workspace_manager):
        """Test successful path validation."""
        workspace_manager.create_workspace("user1", "session1")

        context = WebExecutionContext.create_for_session(
            session_id="session1",
            user_id="user1",
            workspace_manager=workspace_manager,
        )

        valid_path = context.validate_path("artifacts/test.txt")
        assert valid_path == context.workspace_path / "artifacts" / "test.txt"

    def test_validate_path_traversal_blocked(self, workspace_manager):
        """Test path traversal is blocked."""
        workspace_manager.create_workspace("user1", "session1")

        context = WebExecutionContext.create_for_session(
            session_id="session1",
            user_id="user1",
            workspace_manager=workspace_manager,
        )

        with pytest.raises(WorkspaceSecurityError):
            context.validate_path("../other_session/file.txt")

    def test_validate_path_disabled_mode(self, workspace_manager):
        """Test path validation in disabled mode."""
        workspace_manager.create_workspace("user1", "session1")
        workspace_path = workspace_manager.get_workspace_path("user1", "session1")

        context = WebExecutionContext(
            session_id="session1",
            user_id="user1",
            workspace_path=workspace_path,
            workspace_manager=workspace_manager,
            sandbox_mode=SandboxMode.DISABLED,
        )

        # Should not raise even for absolute paths
        result = context.validate_path("/some/path")
        assert result == Path("/some/path").resolve()

    def test_default_blocked_tools(self, workspace_manager):
        """Test default blocked tools in strict mode."""
        context = WebExecutionContext.create_for_session(
            session_id="session1",
            user_id="user1",
            workspace_manager=workspace_manager,
        )

        assert context.is_tool_blocked("process_manager")
        assert not context.is_tool_blocked("read")

    def test_tool_overrides(self, workspace_manager):
        """Test tool parameter overrides."""
        context = WebExecutionContext.create_for_session(
            session_id="session1",
            user_id="user1",
            workspace_manager=workspace_manager,
        )

        overrides = context.get_tool_overrides("bash")
        assert "working_directory" in overrides

    def test_check_file_upload(self, workspace_manager, storage_manager):
        """Test file upload quota check."""
        context = WebExecutionContext.create_for_session(
            session_id="session1",
            user_id="user1",
            workspace_manager=workspace_manager,
            storage_manager=storage_manager,
        )

        # Small file should be allowed
        assert context.check_file_upload(1024)


class MockTool:
    """Mock tool for testing."""

    def __init__(self, name="mock_tool", should_succeed=True):
        self.name = name
        self.description = "A mock tool"
        self.parameters = {"type": "object", "properties": {}}
        self.should_succeed = should_succeed
        self.last_kwargs = None

    async def execute(self, **kwargs):
        self.last_kwargs = kwargs
        from agent_framework.tools.tool_base import ToolResult

        if self.should_succeed:
            return ToolResult(output="Success")
        else:
            return ToolResult(error="Failed")


class TestSandboxedToolWrapper:
    """Tests for SandboxedToolWrapper class."""

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
    def context(self, workspace_manager):
        """Create a WebExecutionContext."""
        return WebExecutionContext.create_for_session(
            session_id="session1",
            user_id="user1",
            workspace_manager=workspace_manager,
        )

    def test_wrapper_properties(self, context):
        """Test wrapper exposes tool properties."""
        tool = MockTool(name="test_tool")
        wrapper = SandboxedToolWrapper(tool, context)

        assert wrapper.name == "test_tool"
        assert wrapper.description == "A mock tool"
        assert wrapper.parameters == tool.parameters

    def test_execute_success(self, context):
        """Test successful tool execution."""
        tool = MockTool()
        wrapper = SandboxedToolWrapper(tool, context)

        result = asyncio.run(wrapper.execute(param1="value1"))

        assert result.error is None
        assert result.output == "Success"
        assert tool.last_kwargs == {"param1": "value1"}

    def test_execute_blocked_tool(self, context):
        """Test blocked tool returns error."""
        tool = MockTool(name="process_manager")
        wrapper = SandboxedToolWrapper(tool, context)

        result = asyncio.run(wrapper.execute())

        assert result.error is not None
        assert "blocked" in result.error.lower()

    def test_path_validation(self, context, workspace_manager):
        """Test path parameters are validated."""
        tool = MockTool()
        wrapper = SandboxedToolWrapper(tool, context)

        # Valid path should work
        result = asyncio.run(wrapper.execute(file_path="artifacts/test.txt"))
        assert result.error is None

    def test_path_traversal_blocked(self, context):
        """Test path traversal is blocked."""
        tool = MockTool()
        wrapper = SandboxedToolWrapper(tool, context)

        result = asyncio.run(wrapper.execute(file_path="../etc/passwd"))

        assert result.error is not None
        assert "security" in result.error.lower()

    def test_bash_command_validation(self, context):
        """Test dangerous bash commands are blocked."""
        tool = MockTool(name="bash")
        wrapper = SandboxedToolWrapper(tool, context)

        # Dangerous command should be blocked
        result = asyncio.run(wrapper.execute(command="rm -rf /"))

        assert result.error is not None
        assert "dangerous" in result.error.lower() or "blocked" in result.error.lower()

    def test_bash_safe_command(self, context):
        """Test safe bash commands are allowed."""
        tool = MockTool(name="bash")
        wrapper = SandboxedToolWrapper(tool, context)

        result = asyncio.run(wrapper.execute(command="ls -la"))

        assert result.error is None

    def test_parameter_overrides_applied(self, context):
        """Test that parameter overrides are applied."""
        tool = MockTool(name="bash")
        wrapper = SandboxedToolWrapper(tool, context)

        asyncio.run(wrapper.execute(command="echo test"))

        # Should have working_directory override applied
        assert "working_directory" in tool.last_kwargs
        assert tool.last_kwargs["working_directory"] == str(context.workspace_path)

    def test_parameter_sanitization(self, context):
        """Test that sensitive parameters are sanitized for logging."""
        tool = MockTool()
        wrapper = SandboxedToolWrapper(tool, context)

        # Create an audit logger mock
        mock_logger = MagicMock()
        context.audit_logger = mock_logger

        asyncio.run(
            wrapper.execute(
                file_path="test.txt",
                password="secret123",
                content="x" * 2000,  # Long content
            )
        )

        # Check that log_tool_execution was called
        mock_logger.log_tool_call.assert_called_once()
        call_args = mock_logger.log_tool_call.call_args
        params = call_args.kwargs.get("parameters", {})

        # Password should be redacted
        assert params.get("password") == "[REDACTED]"
        # Long content should be truncated
        assert "truncated" in str(params.get("content", ""))


class TestSandboxedToolkit:
    """Tests for SandboxedToolkit class."""

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
    def context(self, workspace_manager):
        """Create a WebExecutionContext."""
        return WebExecutionContext.create_for_session(
            session_id="session1",
            user_id="user1",
            workspace_manager=workspace_manager,
        )

    def test_toolkit_wraps_tools(self, context):
        """Test toolkit wraps multiple tools."""
        tools = [
            MockTool(name="tool1"),
            MockTool(name="tool2"),
            MockTool(name="tool3"),
        ]
        toolkit = SandboxedToolkit(tools, context)

        assert len(toolkit.list_tools()) == 3
        assert "tool1" in toolkit.list_tools()
        assert "tool2" in toolkit.list_tools()

    def test_toolkit_get_tool(self, context):
        """Test getting a specific tool."""
        tools = [MockTool(name="read"), MockTool(name="write")]
        toolkit = SandboxedToolkit(tools, context)

        read_tool = toolkit.get("read")
        assert read_tool is not None
        assert read_tool.name == "read"

    def test_toolkit_get_nonexistent(self, context):
        """Test getting a nonexistent tool."""
        toolkit = SandboxedToolkit([], context)

        assert toolkit.get("nonexistent") is None

    def test_toolkit_execute(self, context):
        """Test executing a tool by name."""
        tools = [MockTool(name="test")]
        toolkit = SandboxedToolkit(tools, context)

        result = asyncio.run(toolkit.execute("test", param="value"))

        assert result.error is None
        assert result.output == "Success"

    def test_toolkit_execute_nonexistent(self, context):
        """Test executing a nonexistent tool."""
        toolkit = SandboxedToolkit([], context)

        result = asyncio.run(toolkit.execute("nonexistent"))

        assert result.error is not None
        assert "not found" in result.error.lower()

    def test_toolkit_get_all(self, context):
        """Test getting all wrapped tools."""
        tools = [MockTool(name="tool1"), MockTool(name="tool2")]
        toolkit = SandboxedToolkit(tools, context)

        all_tools = toolkit.get_all()

        assert len(all_tools) == 2
        assert all(isinstance(t, SandboxedToolWrapper) for t in all_tools)
