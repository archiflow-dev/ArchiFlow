"""
Web Execution Context for ArchiFlow Web Backend.

Extends ExecutionContext with web-specific sandbox configuration.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, TYPE_CHECKING, Any, Dict
from enum import Enum
import logging

from agent_framework.runtime.context import ExecutionContext

if TYPE_CHECKING:
    from .workspace_manager import WorkspaceManager
    from .storage_manager import StorageManager
    from .audit_logger import AuditLogger

logger = logging.getLogger(__name__)


class SandboxMode(Enum):
    """Sandbox enforcement modes."""
    STRICT = "strict"       # All paths validated, quotas enforced, full audit
    PERMISSIVE = "permissive"  # Path validation only, no quotas
    DISABLED = "disabled"   # CLI mode, no sandboxing (development only)


@dataclass
class WebExecutionContext(ExecutionContext):
    """
    Extended execution context for web-based agent execution.

    Integrates with WorkspaceManager and StorageManager to provide:
    - Mandatory path sandboxing within session workspace
    - Storage quota enforcement
    - User/session isolation
    - Audit logging

    This context is created by WebAgentRunner and passed to all tools
    via the SandboxedToolWrapper.
    """

    # User/Session identity
    user_id: str = ""

    # Workspace configuration
    workspace_path: Optional[Path] = None
    workspace_manager: Optional['WorkspaceManager'] = field(default=None, repr=False)
    storage_manager: Optional['StorageManager'] = field(default=None, repr=False)
    audit_logger: Optional['AuditLogger'] = field(default=None, repr=False)

    # Sandbox configuration
    sandbox_mode: SandboxMode = SandboxMode.STRICT

    # Tool restrictions
    blocked_tools: set = field(default_factory=set)
    """Tool names that are completely blocked in this context."""

    tool_overrides: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    """Per-tool parameter overrides (e.g., force working_dir for bash)."""

    def __post_init__(self):
        """Validate context after initialization."""
        # Call parent validation
        super().__post_init__()

        # Ensure workspace_path is Path
        if isinstance(self.workspace_path, str):
            self.workspace_path = Path(self.workspace_path)

        # Set default blocked tools for web environment
        if not self.blocked_tools and self.sandbox_mode == SandboxMode.STRICT:
            self.blocked_tools = {
                "process_manager",  # No process management in web
            }

    def validate_path(self, path: str) -> Path:
        """
        Validate that a path is within the sandbox.

        Args:
            path: Relative path to validate

        Returns:
            Absolute path within workspace

        Raises:
            SecurityError: If path escapes workspace
        """
        if self.sandbox_mode == SandboxMode.DISABLED:
            return Path(path).resolve()

        if not self.workspace_manager or not self.workspace_path:
            raise ValueError("WorkspaceManager not configured")

        return self.workspace_manager.validate_path(self.workspace_path, path)

    def check_file_upload(self, size: int) -> bool:
        """
        Check if a file upload is allowed within quotas.

        Args:
            size: File size in bytes

        Returns:
            True if allowed

        Raises:
            StorageLimitError: If quota exceeded
        """
        if self.sandbox_mode == SandboxMode.DISABLED:
            return True

        if self.sandbox_mode == SandboxMode.PERMISSIVE:
            return True  # No quota enforcement in permissive mode

        if not self.storage_manager:
            raise ValueError("StorageManager not configured")

        return self.storage_manager.check_file_upload(
            self.user_id,
            self.session_id,
            size
        )

    def is_tool_blocked(self, tool_name: str) -> bool:
        """Check if a tool is blocked in this context."""
        return tool_name in self.blocked_tools

    def get_tool_overrides(self, tool_name: str) -> Dict[str, Any]:
        """Get parameter overrides for a tool."""
        return self.tool_overrides.get(tool_name, {})

    def log_tool_execution(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        success: bool,
        error: Optional[str] = None
    ) -> None:
        """
        Log a tool execution to the audit log.

        Args:
            tool_name: Name of the tool
            parameters: Tool parameters (sanitized)
            success: Whether execution succeeded
            error: Error message if failed
        """
        if self.audit_logger:
            self.audit_logger.log_tool_call(
                session_id=self.session_id,
                user_id=self.user_id,
                tool_name=tool_name,
                parameters=parameters,
                success=success,
                error=error,
            )

    @classmethod
    def create_for_session(
        cls,
        session_id: str,
        user_id: str,
        workspace_manager: 'WorkspaceManager',
        storage_manager: Optional['StorageManager'] = None,
        audit_logger: Optional['AuditLogger'] = None,
        sandbox_mode: SandboxMode = SandboxMode.STRICT,
    ) -> 'WebExecutionContext':
        """
        Factory method to create a context for a session.

        Args:
            session_id: Session ID
            user_id: User ID
            workspace_manager: WorkspaceManager instance
            storage_manager: Optional StorageManager instance
            audit_logger: Optional AuditLogger instance
            sandbox_mode: Sandbox enforcement mode

        Returns:
            Configured WebExecutionContext
        """
        workspace_path = workspace_manager.get_workspace_path(user_id, session_id)

        # Ensure workspace exists
        if not workspace_path.exists():
            workspace_manager.create_workspace(user_id, session_id)

        return cls(
            session_id=session_id,
            user_id=user_id,
            workspace_path=workspace_path,
            workspace_manager=workspace_manager,
            storage_manager=storage_manager,
            audit_logger=audit_logger,
            sandbox_mode=sandbox_mode,
            working_directory=str(workspace_path),
            allowed_network=True,  # Web agents typically need network
            tool_overrides={
                # Force bash to run in workspace directory
                "bash": {"working_directory": str(workspace_path)},
                "restricted_bash": {"working_directory": str(workspace_path)},
            }
        )
