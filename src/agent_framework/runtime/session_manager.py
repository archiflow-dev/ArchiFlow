"""
Session-scoped runtime manager.

Creates and manages per-session runtime instances with workspace isolation.
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from .base import ToolRuntime
from .manager import RuntimeManager
from .context import ExecutionContext
from .result import ToolResult
from .sandbox import SandboxRuntime, SandboxConfig, SandboxMode

# Import framework interfaces
try:
    from ..storage.quota import StorageQuota
    from ..audit.trail import AuditTrail
except ImportError:
    StorageQuota = None  # type: ignore
    AuditTrail = None  # type: ignore

logger = logging.getLogger(__name__)


class SessionRuntimeManager:
    """
    Per-session runtime manager with workspace isolation.

    Each session gets its own manager with session-specific sandbox runtime.
    Global runtimes (local, remote, mcp) are delegated to the global manager.

    Architecture:
        - Holds reference to global RuntimeManager (singleton)
        - Creates session-specific SandboxRuntime with workspace
        - Routes tool execution based on SecurityPolicy
        - File tools → SandboxRuntime
        - Network tools → LocalRuntime (delegated)
        - Other tools → As configured in SecurityPolicy

    Usage:
        session_manager = SessionRuntimeManager(
            session_id="session_123",
            workspace_path=Path("/workspaces/user_456/session_123"),
            global_manager=global_runtime_manager,
            storage_quota=quota,  # Optional
            audit_trail=trail,    # Optional
            sandbox_mode=SandboxMode.STRICT,
        )

        result = await session_manager.execute_tool(tool, params, context)
    """

    # Tools that should use sandbox (file operations)
    # Note: bash is NOT included here - it has its own command validation
    # and doesn't use file_path parameters in the same way
    SANDBOX_TOOLS = {
        "read",
        "write",
        "edit",
        "multi_edit",
        "glob",
        "grep",
        "list",
    }

    def __init__(
        self,
        session_id: str,
        workspace_path: Path,
        global_manager: RuntimeManager,
        storage_quota: Optional["StorageQuota"] = None,
        audit_trail: Optional["AuditTrail"] = None,
        sandbox_mode: str = SandboxMode.STRICT,
    ):
        """
        Initialize session runtime manager.

        Args:
            session_id: Unique session identifier
            workspace_path: Session workspace directory
            global_manager: Global RuntimeManager for delegating non-sandbox tools
            storage_quota: Optional storage quota enforcement
            audit_trail: Optional audit logging
            sandbox_mode: Sandbox enforcement level
        """
        self.session_id = session_id
        self.workspace_path = workspace_path
        self.global_manager = global_manager
        self.storage_quota = storage_quota
        self.audit_trail = audit_trail

        # Create session-specific sandbox runtime
        self._sandbox_runtime: Optional[SandboxRuntime] = None
        self._initialize_sandbox_runtime(sandbox_mode)

        logger.info(
            f"SessionRuntimeManager created: session={session_id}, "
            f"workspace={workspace_path}, mode={sandbox_mode}"
        )

    def _initialize_sandbox_runtime(self, mode: str) -> None:
        """Create the sandbox runtime for this session."""
        config = SandboxConfig(
            workspace_path=self.workspace_path,
            mode=mode,
        )

        self._sandbox_runtime = SandboxRuntime(
            config=config,
            storage_quota=self.storage_quota,
            audit_trail=self.audit_trail,
        )

    async def execute_tool(
        self,
        tool: Any,
        params: Dict[str, Any],
        context: ExecutionContext,
    ) -> ToolResult:
        """
        Execute a tool using the appropriate runtime.

        Routing logic:
        1. Check if tool is a file tool (needs sandbox)
        2. Check SecurityPolicy for tool's assigned runtime
        3. If "sandbox" or file tool → use session's SandboxRuntime
        4. Otherwise → delegate to global RuntimeManager

        Args:
            tool: Tool to execute
            params: Tool parameters
            context: Execution context

        Returns:
            ToolResult from execution
        """
        tool_name = getattr(tool, "name", str(tool))

        # Determine which runtime to use
        use_sandbox = self._should_use_sandbox(tool_name)

        # Ensure context has correct working directory
        context.working_directory = str(self.workspace_path)

        # Execute
        logger.debug(
            f"Session {self.session_id}: Executing {tool_name} "
            f"with {'sandbox' if use_sandbox else 'global'} runtime"
        )

        if use_sandbox:
            # Use session's sandbox runtime
            return await self._sandbox_runtime.execute(tool, params, context)
        else:
            # Delegate to global manager
            return await self.global_manager.execute_tool(tool, params, context)

    def _should_use_sandbox(self, tool_name: str) -> bool:
        """
        Determine if tool should use sandbox runtime.

        Args:
            tool_name: Name of the tool

        Returns:
            True if should use sandbox, False otherwise
        """
        # File tools always use sandbox
        if tool_name.lower() in self.SANDBOX_TOOLS:
            return True

        # Check SecurityPolicy
        runtime_name = self.global_manager.security_policy.get_runtime_for_tool(
            tool_name
        )

        return runtime_name == "sandbox"

    def get_sandbox_runtime(self) -> SandboxRuntime:
        """Get the session's sandbox runtime."""
        return self._sandbox_runtime

    def get_workspace_path(self) -> Path:
        """Get the session workspace path."""
        return self.workspace_path

    async def health_check(self) -> Dict[str, bool]:
        """Health check for all runtimes."""
        health = {}

        # Check sandbox runtime
        if self._sandbox_runtime:
            health["sandbox"] = await self._sandbox_runtime.health_check()

        # Add global runtime health
        try:
            global_health = await self.global_manager.health_check_all()
            health.update(global_health)
        except Exception as e:
            logger.warning(f"Error checking global runtime health: {e}")

        return health

    async def cleanup(self) -> None:
        """Cleanup session runtime resources."""
        if self._sandbox_runtime:
            await self._sandbox_runtime.cleanup()
        logger.info(f"SessionRuntimeManager cleaned up: session={self.session_id}")
