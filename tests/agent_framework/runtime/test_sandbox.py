"""
Tests for SandboxRuntime and SessionRuntimeManager.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, AsyncMock

from agent_framework.runtime.base import ToolRuntime
from agent_framework.runtime.context import ExecutionContext
from agent_framework.runtime.result import ToolResult
from agent_framework.runtime.manager import RuntimeManager
from agent_framework.runtime.security import SecurityPolicy
from agent_framework.runtime.local import LocalRuntime
from agent_framework.runtime.sandbox import (
    SandboxRuntime,
    SandboxConfig,
    SandboxMode,
)
from agent_framework.runtime.session_manager import SessionRuntimeManager
from agent_framework.runtime.exceptions import SecurityViolation, ResourceLimitError

from agent_framework.storage.memory import InMemoryQuota
from agent_framework.audit.null import NullAuditTrail
from agent_framework.audit.logger import LoggerAuditTrail


class MockTool:
    """Mock tool for testing."""

    def __init__(self, name, execute_result=None):
        self.name = name
        self._execute_result = execute_result or ToolResult.success_result("OK")

    async def execute(self, **kwargs):
        return self._execute_result


class TestSandboxConfig:
    """Tests for SandboxConfig dataclass."""

    def test_initialization(self):
        """Test sandbox config initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = SandboxConfig(
                workspace_path=Path(tmpdir),
                mode=SandboxMode.STRICT,
            )

            assert config.workspace_path == Path(tmpdir)
            assert config.mode == SandboxMode.STRICT

    def test_initialization_with_invalid_mode(self):
        """Test that invalid mode raises error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(ValueError):
                SandboxConfig(
                    workspace_path=Path(tmpdir),
                    mode="invalid_mode",
                )


class TestSandboxMode:
    """Tests for SandboxMode."""

    def test_values(self):
        """Test mode values."""
        assert SandboxMode.STRICT == "strict"
        assert SandboxMode.PERMISSIVE == "permissive"
        assert SandboxMode.DISABLED == "disabled"

    def test_is_valid(self):
        """Test mode validation."""
        assert SandboxMode.is_valid("strict") is True
        assert SandboxMode.is_valid("permissive") is True
        assert SandboxMode.is_valid("disabled") is True
        assert SandboxMode.is_valid("invalid") is False


class TestSandboxRuntime:
    """Tests for SandboxRuntime."""

    def test_initialization(self):
        """Test sandbox runtime initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = SandboxConfig(
                workspace_path=Path(tmpdir),
                mode=SandboxMode.STRICT,
            )

            runtime = SandboxRuntime(config=config)

            assert runtime.config == config
            assert runtime.storage_quota is None
            assert runtime.audit_trail is None
            assert isinstance(runtime._local_runtime, LocalRuntime)

    def test_initialization_with_optional_dependencies(self):
        """Test initialization with storage quota and audit trail."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = SandboxConfig(workspace_path=Path(tmpdir))

            quota = InMemoryQuota(limit_bytes=1000)
            audit = NullAuditTrail()

            runtime = SandboxRuntime(
                config=config,
                storage_quota=quota,
                audit_trail=audit,
            )

            assert runtime.storage_quota == quota
            assert runtime.audit_trail == audit

    def test_get_workspace_path(self):
        """Test getting workspace path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = SandboxConfig(workspace_path=Path(tmpdir))

            runtime = SandboxRuntime(config=config)

            assert runtime.get_workspace_path() == Path(tmpdir).resolve()

    @pytest.mark.asyncio
    async def test_execute_tool_success(self):
        """Test successful tool execution."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = SandboxConfig(
                workspace_path=Path(tmpdir),
                mode=SandboxMode.STRICT,
            )

            runtime = SandboxRuntime(config=config)

            # Mock tool
            tool = MockTool("read", ToolResult.success_result("File content"))

            # Create test file
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("content")

            # Execute
            context = ExecutionContext(
                session_id="session_1",
                timeout=30,
            )

            result = await runtime.execute(
                tool,
                {"file_path": "test.txt"},
                context,
            )

            assert result.success is True

    @pytest.mark.asyncio
    async def test_execute_tool_path_validation_blocks_traversal(self):
        """Test that path traversal is blocked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = SandboxConfig(
                workspace_path=Path(tmpdir),
                mode=SandboxMode.STRICT,
            )

            runtime = SandboxRuntime(config=config)

            tool = MockTool("read")

            context = ExecutionContext(
                session_id="session_1",
                timeout=30,
            )

            # Try to access file outside workspace
            with pytest.raises(SecurityViolation) as exc_info:
                await runtime.execute(
                    tool,
                    {"file_path": "../../../etc/passwd"},
                    context,
                )

            assert "escapes workspace" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_execute_tool_path_validation_blocks_absolute_path(self):
        """Test that absolute paths are blocked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = SandboxConfig(
                workspace_path=Path(tmpdir),
                mode=SandboxMode.STRICT,
            )

            runtime = SandboxRuntime(config=config)

            tool = MockTool("read")

            context = ExecutionContext(
                session_id="session_1",
                timeout=30,
            )

            # Try absolute path
            with pytest.raises(SecurityViolation) as exc_info:
                await runtime.execute(
                    tool,
                    {"file_path": "/etc/passwd"},
                    context,
                )

            # Path validator returns "escapes workspace" error for absolute paths
            assert "escapes" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_execute_tool_command_validation_blocks_dangerous(self):
        """Test that dangerous bash commands are blocked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = SandboxConfig(
                workspace_path=Path(tmpdir),
                mode=SandboxMode.STRICT,
            )

            runtime = SandboxRuntime(config=config)

            tool = MockTool("bash")

            context = ExecutionContext(
                session_id="session_1",
                timeout=30,
            )

            # Try rm -rf /
            with pytest.raises(SecurityViolation):
                await runtime.execute(
                    tool,
                    {"command": "rm -rf /"},
                    context,
                )

    @pytest.mark.asyncio
    async def test_execute_tool_with_storage_quota(self):
        """Test storage quota enforcement."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = SandboxConfig(
                workspace_path=Path(tmpdir),
                mode=SandboxMode.STRICT,
            )

            quota = InMemoryQuota(limit_bytes=100)

            runtime = SandboxRuntime(
                config=config,
                storage_quota=quota,
            )

            tool = MockTool("write")

            context = ExecutionContext(
                session_id="session_1",
                timeout=30,
            )

            # Try to write beyond quota
            with pytest.raises(ResourceLimitError):
                await runtime.execute(
                    tool,
                    {"content": "x" * 200},  # Exceeds 100 byte quota
                    context,
                )

    @pytest.mark.asyncio
    async def test_execute_tool_with_audit_logging(self):
        """Test that execution is logged."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = SandboxConfig(
                workspace_path=Path(tmpdir),
                mode=SandboxMode.STRICT,
            )

            # Create mock audit trail
            audit = Mock()
            audit.log_execution = AsyncMock()

            runtime = SandboxRuntime(
                config=config,
                audit_trail=audit,
            )

            tool = MockTool("read", ToolResult.success_result("content"))

            context = ExecutionContext(
                session_id="session_1",
                timeout=30,
            )

            # Create test file
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("content")

            # Execute
            await runtime.execute(
                tool,
                {"file_path": "test.txt"},
                context,
            )

            # Verify audit was called
            audit.log_execution.assert_called_once()
            call_args = audit.log_execution.call_args

            assert call_args[1]["tool_name"] == "read"
            assert call_args[1]["success"] is True
            assert "params" in call_args[1]

    @pytest.mark.asyncio
    async def test_execute_tool_sanitizes_sensitive_params(self):
        """Test that sensitive parameters are redacted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = SandboxConfig(
                workspace_path=Path(tmpdir),
                mode=SandboxMode.STRICT,
            )

            # Create mock audit trail
            audit = Mock()
            audit.log_execution = AsyncMock()

            runtime = SandboxRuntime(
                config=config,
                audit_trail=audit,
            )

            tool = MockTool("api_call")

            context = ExecutionContext(
                session_id="session_1",
                timeout=30,
            )

            # Execute with sensitive params
            await runtime.execute(
                tool,
                {
                    "endpoint": "/api/data",
                    "api_key": "secret_key",
                    "password": "my_password",
                },
                context,
            )

            # Verify sensitive data was redacted
            call_args = audit.log_execution.call_args
            params = call_args[1]["params"]

            assert "[REDACTED]" in params["api_key"]
            assert "[REDACTED]" in params["password"]
            assert params["endpoint"] == "/api/data"  # Non-sensitive preserved

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test runtime health check."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = SandboxConfig(workspace_path=Path(tmpdir))

            runtime = SandboxRuntime(config=config)

            health = await runtime.health_check()

            assert health is True

    @pytest.mark.asyncio
    async def test_cleanup(self):
        """Test runtime cleanup."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = SandboxConfig(workspace_path=Path(tmpdir))

            runtime = SandboxRuntime(config=config)

            # Should not raise
            await runtime.cleanup()

    def test_is_file_tool(self):
        """Test file tool detection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = SandboxConfig(workspace_path=Path(tmpdir))

            runtime = SandboxRuntime(config=config)

            # File tools
            assert runtime._is_file_tool("read") is True
            assert runtime._is_file_tool("write") is True
            assert runtime._is_file_tool("edit") is True
            assert runtime._is_file_tool("glob") is True

            # Non-file tools
            assert runtime._is_file_tool("bash") is False
            assert runtime._is_file_tool("web_search") is False
            assert runtime._is_file_tool("web_fetch") is False

    def test_is_bash_tool(self):
        """Test bash tool detection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = SandboxConfig(workspace_path=Path(tmpdir))

            runtime = SandboxRuntime(config=config)

            # Bash tools
            assert runtime._is_bash_tool("bash") is True
            assert runtime._is_bash_tool("restricted_bash") is True

            # Non-bash tools
            assert runtime._is_bash_tool("read") is False
            assert runtime._is_bash_tool("write") is False

    def test_is_path_param(self):
        """Test path parameter detection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = SandboxConfig(workspace_path=Path(tmpdir))

            runtime = SandboxRuntime(config=config)

            # Path parameters
            assert runtime._is_path_param("file_path") is True
            assert runtime._is_path_param("path") is True
            assert runtime._is_path_param("directory") is True
            assert runtime._is_path_param("source") is True
            assert runtime._is_path_param("destination") is True

            # Not path parameters
            assert runtime._is_path_param("content") is False
            assert runtime._is_path_param("command") is False
            # working_directory is explicitly excluded
            assert runtime._is_path_param("working_directory") is False


class TestSessionRuntimeManager:
    """Tests for SessionRuntimeManager."""

    def test_initialization(self):
        """Test session manager initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            global_manager = RuntimeManager()
            global_manager.register_runtime(
                "local",
                LocalRuntime(),
            )

            manager = SessionRuntimeManager(
                session_id="session_123",
                workspace_path=Path(tmpdir),
                global_manager=global_manager,
                sandbox_mode=SandboxMode.STRICT,
            )

            assert manager.session_id == "session_123"
            assert manager.workspace_path == Path(tmpdir).resolve()
            assert manager.global_manager == global_manager
            assert manager._sandbox_runtime is not None

    def test_initialization_with_optional_dependencies(self):
        """Test initialization with storage quota and audit trail."""
        with tempfile.TemporaryDirectory() as tmpdir:
            global_manager = RuntimeManager()

            quota = InMemoryQuota(limit_bytes=1000)
            audit = NullAuditTrail()

            manager = SessionRuntimeManager(
                session_id="session_123",
                workspace_path=Path(tmpdir),
                global_manager=global_manager,
                storage_quota=quota,
                audit_trail=audit,
                sandbox_mode=SandboxMode.PERMISSIVE,
            )

            assert manager.storage_quota == quota
            assert manager.audit_trail == audit

    def test_get_sandbox_runtime(self):
        """Test getting sandbox runtime."""
        with tempfile.TemporaryDirectory() as tmpdir:
            global_manager = RuntimeManager()

            manager = SessionRuntimeManager(
                session_id="session_123",
                workspace_path=Path(tmpdir),
                global_manager=global_manager,
            )

            sandbox = manager.get_sandbox_runtime()

            assert isinstance(sandbox, SandboxRuntime)
            assert sandbox.get_workspace_path() == Path(tmpdir).resolve()

    def test_get_workspace_path(self):
        """Test getting workspace path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            global_manager = RuntimeManager()

            manager = SessionRuntimeManager(
                session_id="session_123",
                workspace_path=Path(tmpdir),
                global_manager=global_manager,
            )

            assert manager.get_workspace_path() == Path(tmpdir).resolve()

    @pytest.mark.asyncio
    async def test_execute_file_tool_uses_sandbox(self):
        """Test that file tools use sandbox runtime."""
        with tempfile.TemporaryDirectory() as tmpdir:
            global_manager = RuntimeManager()
            global_manager.register_runtime(
                "local",
                LocalRuntime(),
            )

            manager = SessionRuntimeManager(
                session_id="session_123",
                workspace_path=Path(tmpdir),
                global_manager=global_manager,
            )

            # Create a mock sandbox runtime
            sandbox_result = ToolResult.success_result("sandbox executed")
            manager._sandbox_runtime = Mock()
            manager._sandbox_runtime.execute = AsyncMock(return_value=sandbox_result)

            tool = MockTool("read")

            context = ExecutionContext(
                session_id="session_123",
                timeout=30,
            )

            result = await manager.execute_tool(
                tool,
                {"file_path": "test.txt"},
                context,
            )

            # Verify sandbox was used
            manager._sandbox_runtime.execute.assert_called_once()
            assert result == sandbox_result

    @pytest.mark.asyncio
    async def test_execute_non_file_tool_delegates_to_global(self):
        """Test that non-file tools delegate to global manager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            global_manager = RuntimeManager()

            # Mock the execute_tool method
            global_result = ToolResult.success_result("global executed")
            global_manager.execute_tool = AsyncMock(return_value=global_result)

            manager = SessionRuntimeManager(
                session_id="session_123",
                workspace_path=Path(tmpdir),
                global_manager=global_manager,
            )

            tool = MockTool("web_search")

            context = ExecutionContext(
                session_id="session_123",
                timeout=30,
            )

            result = await manager.execute_tool(
                tool,
                {"query": "test"},
                context,
            )

            # Verify global manager was used
            global_manager.execute_tool.assert_called_once_with(
                tool,
                {"query": "test"},
                context,
            )
            assert result == global_result

    def test_should_use_sandbox_for_file_tools(self):
        """Test sandbox routing logic for file tools."""
        with tempfile.TemporaryDirectory() as tmpdir:
            global_manager = RuntimeManager(
                security_policy=SecurityPolicy(
                    default_runtime="local",
                )
            )

            manager = SessionRuntimeManager(
                session_id="session_123",
                workspace_path=Path(tmpdir),
                global_manager=global_manager,
            )

            # File tools should use sandbox
            assert manager._should_use_sandbox("read") is True
            assert manager._should_use_sandbox("write") is True
            assert manager._should_use_sandbox("edit") is True
            assert manager._should_use_sandbox("glob") is True

            # Non-file tools should not
            assert manager._should_use_sandbox("bash") is False
            assert manager._should_use_sandbox("web_search") is False

    def test_should_use_sandbox_respects_security_policy(self):
        """Test that SecurityPolicy is respected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create policy that routes "bash" to "sandbox"
            # (bash is not in SANDBOX_TOOLS by default)
            policy = SecurityPolicy(
                tool_runtime_map={
                    "bash": "sandbox",
                },
            )

            global_manager = RuntimeManager(security_policy=policy)

            manager = SessionRuntimeManager(
                session_id="session_123",
                workspace_path=Path(tmpdir),
                global_manager=global_manager,
            )

            # "bash" should use sandbox (from policy, even though not in SANDBOX_TOOLS)
            assert manager._should_use_sandbox("bash") is True

            # "web_search" should not use sandbox (not in policy and not in SANDBOX_TOOLS)
            assert manager._should_use_sandbox("web_search") is False

            # "read" should still use sandbox (it's in SANDBOX_TOOLS)
            assert manager._should_use_sandbox("read") is True

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health check includes sandbox and global runtimes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            global_manager = RuntimeManager()
            global_manager.register_runtime(
                "local",
                LocalRuntime(),
            )

            manager = SessionRuntimeManager(
                session_id="session_123",
                workspace_path=Path(tmpdir),
                global_manager=global_manager,
            )

            health = await manager.health_check()

            # Should have health status for sandbox and local
            assert "sandbox" in health
            assert "local" in health
            assert health["sandbox"] is True
            assert health["local"] is True

    @pytest.mark.asyncio
    async def test_cleanup(self):
        """Test session manager cleanup."""
        with tempfile.TemporaryDirectory() as tmpdir:
            global_manager = RuntimeManager()

            manager = SessionRuntimeManager(
                session_id="session_123",
                workspace_path=Path(tmpdir),
                global_manager=global_manager,
            )

            # Should not raise
            await manager.cleanup()


class TestRuntimeManagerIntegration:
    """Integration tests for RuntimeManager.create_session_manager()."""

    def test_create_session_manager(self):
        """Test that RuntimeManager can create session managers."""
        with tempfile.TemporaryDirectory() as tmpdir:
            global_manager = RuntimeManager()

            session_manager = global_manager.create_session_manager(
                session_id="session_123",
                workspace_path=Path(tmpdir),
            )

            assert isinstance(session_manager, SessionRuntimeManager)
            assert session_manager.session_id == "session_123"
            assert session_manager.workspace_path == Path(tmpdir).resolve()

    def test_create_session_manager_with_dependencies(self):
        """Test creating session manager with all dependencies."""
        with tempfile.TemporaryDirectory() as tmpdir:
            global_manager = RuntimeManager()

            quota = InMemoryQuota(limit_bytes=1000)
            audit = NullAuditTrail()

            session_manager = global_manager.create_session_manager(
                session_id="session_123",
                workspace_path=Path(tmpdir),
                storage_quota=quota,
                audit_trail=audit,
                sandbox_mode=SandboxMode.PERMISSIVE,
            )

            assert session_manager.storage_quota == quota
            assert session_manager.audit_trail == audit

            # Verify sandbox has the dependencies
            sandbox = session_manager.get_sandbox_runtime()
            assert sandbox.storage_quota == quota
            assert sandbox.audit_trail == audit
            assert sandbox.config.mode == SandboxMode.PERMISSIVE
