"""
Sandbox Runtime for secure tool execution.

Enforces workspace isolation, path validation, command filtering,
and storage quotas.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from .base import ToolRuntime
from .context import ExecutionContext
from .result import ToolResult
from .local import LocalRuntime
from .validation.path_validator import PathValidator, PathValidationError
from .validation.command_validator import CommandValidator, CommandValidationError
from .exceptions import SecurityViolation, ResourceLimitError

# Import framework interfaces
try:
    from ..storage.quota import StorageQuota
    from ..audit.trail import AuditTrail
except ImportError:
    # For standalone usage
    StorageQuota = None  # type: ignore
    AuditTrail = None  # type: ignore

logger = logging.getLogger(__name__)


class SandboxMode:
    """Sandbox enforcement level."""
    STRICT = "strict"  # All checks enabled
    PERMISSIVE = "permissive"  # Only critical checks
    DISABLED = "disabled"  # No checks (for testing)

    VALUES = [STRICT, PERMISSIVE, DISABLED]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if mode value is valid."""
        return value in cls.VALUES


@dataclass
class SandboxConfig:
    """Configuration for sandbox runtime."""

    workspace_path: Path
    mode: str = SandboxMode.STRICT
    allowed_extensions: Optional[set] = None
    max_file_size_mb: Optional[int] = None
    allowed_commands: Optional[set] = None
    blocked_patterns: Optional[set] = None

    def __post_init__(self):
        """Validate configuration."""
        if not SandboxMode.is_valid(self.mode):
            raise ValueError(f"Invalid sandbox mode: {self.mode}")


class SandboxRuntime(ToolRuntime):
    """
    Runtime that executes tools with sandbox enforcement.

    Responsibilities:
    1. Path validation - Ensures all paths stay within workspace
    2. Command filtering - Blocks dangerous bash commands
    3. Storage quota - Enforces workspace size limits
    4. Audit logging - Records all tool executions

    Uses composition over inheritance - wraps LocalRuntime internally.

    Usage:
        runtime = SandboxRuntime(
            config=SandboxConfig(
                workspace_path=Path("/workspace/session_123"),
                mode=SandboxMode.STRICT,
            ),
            storage_quota=storage_quota,  # Optional
            audit_trail=audit_trail,      # Optional
        )

        result = await runtime.execute(tool, params, context)
    """

    # Parameters that contain file paths and need validation
    PATH_PARAMETERS = {
        "file_path",
        "path",
        "directory",
        "source",
        "destination",
        "target",
        "output_path",
        "input_path",
    }

    # Tools that operate on files
    FILE_TOOLS = {
        "read",
        "write",
        "edit",
        "multi_edit",
        "glob",
        "grep",
        "list",
    }

    # Tools that execute bash commands
    BASH_TOOLS = {
        "bash",
        "restricted_bash",
    }

    def __init__(
        self,
        config: SandboxConfig,
        storage_quota: Optional["StorageQuota"] = None,
        audit_trail: Optional["AuditTrail"] = None,
    ):
        """
        Initialize sandbox runtime.

        Args:
            config: Sandbox configuration
            storage_quota: Optional storage quota enforcement
            audit_trail: Optional audit logging
        """
        self.config = config
        self.storage_quota = storage_quota
        self.audit_trail = audit_trail

        # Create internal local runtime for actual execution
        self._local_runtime = LocalRuntime(
            enable_resource_monitoring=True
        )

        # Create validators
        self._path_validator = PathValidator(
            workspace_path=config.workspace_path,
            mode=config.mode,
        )
        self._command_validator = CommandValidator(
            mode=config.mode,
            allowed_commands=config.allowed_commands,
            blocked_patterns=config.blocked_patterns,
        )

        logger.info(
            f"SandboxRuntime initialized: workspace={config.workspace_path}, "
            f"mode={config.mode}"
        )

    async def execute(
        self,
        tool: Any,
        params: Dict[str, Any],
        context: ExecutionContext,
    ) -> ToolResult:
        """
        Execute a tool with sandbox enforcement.

        Args:
            tool: Tool to execute
            params: Tool parameters
            context: Execution context

        Returns:
            ToolResult from execution

        Raises:
            SecurityViolation: If sandbox rules violated
            ResourceLimitError: If storage quota exceeded
        """
        tool_name = getattr(tool, "name", str(tool))

        # Phase 1: Pre-execution validation
        try:
            validated_params = await self._validate_execution(tool, params)
        except PathValidationError as e:
            # Convert to SecurityViolation
            raise SecurityViolation(str(e), "path_violation") from e
        except CommandValidationError as e:
            # Convert to SecurityViolation
            raise SecurityViolation(str(e), "command_violation") from e
        except Exception as e:
            # Check if it's a QuotaExceededError (from storage module)
            if "QuotaExceededError" in type(e).__name__:
                # Convert to ResourceLimitError
                await self._audit_execution(
                    tool_name,
                    params,
                    success=False,
                    error="Quota exceeded",
                )
                raise ResourceLimitError(
                    str(e),
                    "storage",
                    limit=getattr(e, "limit", 0),
                    actual=getattr(e, "current_usage", 0)
                ) from e
            raise

        # Calculate estimated size for quota update after execution
        is_write = self._is_write_operation(tool_name, validated_params)
        estimated_size = self._estimate_size(tool_name, validated_params) if is_write else 0

        # Phase 2: Execute via local runtime
        result = await self._local_runtime.execute(tool, validated_params, context)

        # Phase 3: Post-execution quota update (for successful write operations)
        if result.success and is_write and self.storage_quota and estimated_size > 0:
            await self.storage_quota.reserve_space(
                session_id=context.session_id or "unknown",
                workspace_path=self.config.workspace_path,
                bytes_to_reserve=estimated_size,
            )

        # Phase 4: Post-execution audit
        await self._audit_execution(
            tool_name,
            validated_params,
            success=result.success,
            error=result.error,
        )

        return result

    async def _validate_execution(
        self,
        tool: Any,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Validate tool execution against sandbox rules.

        Args:
            tool: Tool to validate
            params: Tool parameters

        Returns:
            Validated (possibly modified) parameters

        Raises:
            SecurityViolation: If validation fails
            ResourceLimitError: If quota exceeded
        """
        tool_name = getattr(tool, "name", str(tool))
        validated_params = params.copy()

        # Path validation for file tools
        if self._is_file_tool(tool_name):
            for param_name, param_value in params.items():
                if self._is_path_param(param_name) and isinstance(param_value, str):
                    # Validate and rewrite path
                    validated_path = self._path_validator.validate(param_value)
                    # Store as relative path for consistency
                    validated_params[param_name] = str(
                        validated_path.relative_to(self.config.workspace_path)
                    )

        # Command validation for bash tools
        if self._is_bash_tool(tool_name):
            command = params.get("command", "")
            if command:  # Only validate if command provided
                self._command_validator.validate(command)

        # Storage quota check
        if self.storage_quota and self._is_write_operation(tool_name, params):
            # Estimate size (rough estimate for write operations)
            estimated_size = self._estimate_size(tool_name, params)
            if estimated_size > 0:
                has_quota = await self.storage_quota.check_quota(
                    session_id="unknown",  # Session not known at this level
                    workspace_path=self.config.workspace_path,
                    additional_bytes=estimated_size,
                )
                if not has_quota:
                    from ..storage.quota import QuotaExceededError
                    current = self.storage_quota.get_usage(self.config.workspace_path)
                    limit = self.storage_quota.get_limit()
                    raise QuotaExceededError(
                        "Storage quota would be exceeded",
                        current_usage=current,
                        requested_bytes=estimated_size,
                        limit=limit,
                    )

        return validated_params

    def _is_file_tool(self, tool_name: str) -> bool:
        """Check if tool operates on files."""
        return tool_name.lower() in self.FILE_TOOLS

    def _is_bash_tool(self, tool_name: str) -> bool:
        """Check if tool is a bash execution tool."""
        return tool_name.lower() in self.BASH_TOOLS

    def _is_path_param(self, param_name: str) -> bool:
        """Check if parameter is a path."""
        # Exclude working_directory - it's set via context
        if param_name.lower() == "working_directory":
            return False
        return param_name.lower() in self.PATH_PARAMETERS

    def _is_write_operation(self, tool_name: str, params: Dict[str, Any]) -> bool:
        """Check if operation will write data."""
        # Write operations
        if tool_name in {"write", "edit", "multi_edit"}:
            return True

        # Check for write parameters
        for param in params:
            if "content" in param.lower() or "data" in param.lower():
                return True

        return False

    def _estimate_size(self, tool_name: str, params: Dict[str, Any]) -> int:
        """Estimate size of operation for quota check."""
        # For write operations, check content size
        if tool_name == "write":
            content = params.get("content", "")
            if isinstance(content, str):
                return len(content.encode("utf-8"))
        elif tool_name == "edit":
            new_content = params.get("new_text", "")
            if isinstance(new_content, str):
                return len(new_content.encode("utf-8"))

        # Default: assume 1KB
        return 1024

    async def _audit_execution(
        self,
        tool_name: str,
        params: Dict[str, Any],
        success: bool,
        error: Optional[str] = None,
    ) -> None:
        """Log tool execution to audit trail."""
        if self.audit_trail is None:
            return

        # Sanitize params for logging (remove sensitive data)
        sanitized = self._sanitize_params(params)

        # Add workspace context
        metadata = {
            "workspace": str(self.config.workspace_path),
            "mode": self.config.mode,
        }

        await self.audit_trail.log_execution(
            tool_name=tool_name,
            params=sanitized,
            success=success,
            error=error,
            **metadata,
        )

    def _sanitize_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive data from parameters."""
        sanitized = {}
        sensitive_keys = {"password", "secret", "token", "key", "api_key"}

        for key, value in params.items():
            if any(s in key.lower() for s in sensitive_keys):
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, str) and len(value) > 1000:
                sanitized[key] = f"{value[:100]}...[truncated {len(value)} chars]"
            else:
                sanitized[key] = value

        return sanitized

    async def health_check(self) -> bool:
        """Check if sandbox runtime is healthy."""
        return (
            self._local_runtime is not None
            and await self._local_runtime.health_check()
        )

    async def cleanup(self) -> None:
        """Cleanup sandbox runtime resources."""
        await self._local_runtime.cleanup()
        logger.info("SandboxRuntime cleaned up")

    def get_workspace_path(self) -> Path:
        """Get the workspace path for this runtime."""
        return self.config.workspace_path
