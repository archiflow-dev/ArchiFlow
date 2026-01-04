"""
Sandboxed Tool Wrapper for ArchiFlow Web Backend.

Wraps agent framework tools with sandbox enforcement.
"""

from typing import Any, Dict, Optional, Set
from pathlib import Path
import logging
import re

from agent_framework.tools.tool_base import BaseTool, ToolResult

from .web_context import WebExecutionContext, SandboxMode
from .workspace_manager import WorkspaceSecurityError

logger = logging.getLogger(__name__)


# Parameters that contain file paths and need validation
PATH_PARAMETERS = {
    "file_path",
    "path",
    "directory",
    "source",
    "destination",
    "working_directory",
    "target",
    "output_path",
    "input_path",
}


class SandboxViolationError(Exception):
    """Raised when a tool attempts to violate sandbox constraints."""
    pass


class SandboxedToolWrapper:
    """
    Wraps a tool with sandbox enforcement.

    This wrapper:
    - Validates all path parameters against workspace
    - Enforces storage quotas
    - Blocks dangerous tools
    - Applies parameter overrides
    - Logs all executions to audit log

    Usage:
        context = WebExecutionContext.create_for_session(...)
        read_tool = ReadTool()
        sandboxed = SandboxedToolWrapper(read_tool, context)
        result = await sandboxed.execute(file_path="data/file.txt")
    """

    def __init__(
        self,
        tool: BaseTool,
        context: WebExecutionContext,
    ):
        """
        Initialize the sandboxed wrapper.

        Args:
            tool: The tool to wrap
            context: Web execution context with sandbox config
        """
        self.tool = tool
        self.context = context

    @property
    def name(self) -> str:
        """Get the wrapped tool's name."""
        return self.tool.name

    @property
    def description(self) -> str:
        """Get the wrapped tool's description."""
        return self.tool.description

    @property
    def parameters(self) -> Dict:
        """Get the wrapped tool's parameters schema."""
        return self.tool.parameters

    def _is_path_parameter(self, param_name: str) -> bool:
        """Check if a parameter is a path that needs validation."""
        # Note: working_directory is handled specially via overrides
        # and should not be validated as a user-provided path
        if param_name.lower() == "working_directory":
            return False
        return param_name.lower() in PATH_PARAMETERS

    def _validate_path(self, path: str) -> str:
        """
        Validate and potentially rewrite a path.

        Args:
            path: The path to validate

        Returns:
            The validated (possibly rewritten) path

        Raises:
            SandboxViolationError: If path escapes sandbox
        """
        if self.context.sandbox_mode == SandboxMode.DISABLED:
            return path

        try:
            validated = self.context.validate_path(path)
            # Return the path relative to workspace for consistency
            return str(validated.relative_to(self.context.workspace_path))
        except (WorkspaceSecurityError, ValueError) as e:
            raise SandboxViolationError(f"Path security violation: {e}")

    def _sanitize_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize parameters for logging (remove sensitive data).

        Args:
            parameters: Original parameters

        Returns:
            Sanitized copy safe for logging
        """
        sanitized = {}
        sensitive_patterns = ["password", "secret", "token", "key", "auth"]

        for key, value in parameters.items():
            # Check if key contains sensitive patterns
            if any(p in key.lower() for p in sensitive_patterns):
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, str) and len(value) > 1000:
                # Truncate long values (like file content)
                sanitized[key] = f"{value[:100]}...[truncated {len(value)} chars]"
            else:
                sanitized[key] = value

        return sanitized

    def _apply_overrides(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply tool-specific parameter overrides.

        Args:
            parameters: Original parameters

        Returns:
            Parameters with overrides applied
        """
        overrides = self.context.get_tool_overrides(self.tool.name)
        if overrides:
            parameters = {**parameters, **overrides}
        return parameters

    def _validate_bash_command(self, command: str) -> None:
        """
        Additional validation for bash commands.

        Args:
            command: The bash command to validate

        Raises:
            SandboxViolationError: If command is dangerous
        """
        if self.context.sandbox_mode == SandboxMode.DISABLED:
            return

        # Block dangerous patterns
        dangerous_patterns = [
            r"\brm\s+-rf\s+/",  # rm -rf /
            r"\bdd\s+if=",      # dd commands
            r"\bmkfs\b",        # Filesystem creation
            r"\bformat\b",      # Windows format
            r">\s*/dev/",       # Writing to devices
            r"\bsudo\b",        # Sudo commands
            r"\bchmod\s+777\b", # World writable
            r"\bcurl\b.*\|\s*bash",  # Pipe to bash
            r"\bwget\b.*\|\s*bash",  # Pipe to bash
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                raise SandboxViolationError(
                    f"Dangerous command pattern blocked: {pattern}"
                )

    async def execute(self, **kwargs) -> ToolResult:
        """
        Execute the tool with sandbox enforcement.

        Args:
            **kwargs: Tool parameters

        Returns:
            ToolResult from the wrapped tool
        """
        tool_name = self.tool.name

        # Check if tool is blocked
        if self.context.is_tool_blocked(tool_name):
            error = f"Tool '{tool_name}' is blocked in this context"
            self.context.log_tool_execution(
                tool_name=tool_name,
                parameters={},
                success=False,
                error=error,
            )
            return ToolResult(error=error)

        try:
            # Apply parameter overrides
            kwargs = self._apply_overrides(kwargs)

            # Validate path parameters
            for param_name, param_value in list(kwargs.items()):
                if self._is_path_parameter(param_name) and isinstance(param_value, str):
                    try:
                        # Validate the path is within sandbox
                        self.context.validate_path(param_value)
                    except (WorkspaceSecurityError, ValueError) as e:
                        error = f"Security violation in {param_name}: {e}"
                        self.context.log_tool_execution(
                            tool_name=tool_name,
                            parameters=self._sanitize_parameters(kwargs),
                            success=False,
                            error=error,
                        )
                        return ToolResult(error=error)

            # Special handling for bash tool
            if tool_name in ("bash", "restricted_bash"):
                command = kwargs.get("command", "")
                try:
                    self._validate_bash_command(command)
                except SandboxViolationError as e:
                    self.context.log_tool_execution(
                        tool_name=tool_name,
                        parameters=self._sanitize_parameters(kwargs),
                        success=False,
                        error=str(e),
                    )
                    return ToolResult(error=str(e))

            # Execute the tool
            result = await self.tool.execute(**kwargs)

            # Log execution
            self.context.log_tool_execution(
                tool_name=tool_name,
                parameters=self._sanitize_parameters(kwargs),
                success=result.error is None,
                error=result.error,
            )

            return result

        except Exception as e:
            error = f"Unexpected error: {str(e)}"
            logger.exception(f"Error executing tool {tool_name}")
            self.context.log_tool_execution(
                tool_name=tool_name,
                parameters=self._sanitize_parameters(kwargs),
                success=False,
                error=error,
            )
            return ToolResult(error=error)

    def to_llm_schema(self) -> Dict:
        """Get the tool schema for LLM function calling."""
        return self.tool.to_llm_schema() if hasattr(self.tool, 'to_llm_schema') else {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


class SandboxedToolRegistry:
    """
    A non-singleton tool registry for sandboxed sessions.

    Unlike the global ToolRegistry (singleton), this creates a
    per-session registry that holds only sandboxed tools.
    This ensures RuntimeExecutor uses sandboxed versions.
    """

    def __init__(self):
        """Initialize empty registry."""
        self.tools: Dict[str, SandboxedToolWrapper] = {}

    def register(self, tool: SandboxedToolWrapper) -> None:
        """Register a sandboxed tool."""
        self.tools[tool.name] = tool

    def get(self, name: str) -> Optional[SandboxedToolWrapper]:
        """Get a tool by name."""
        return self.tools.get(name)

    def list_tools(self) -> list:
        """Get all registered tools."""
        return list(self.tools.values())

    def to_llm_schema(self, tool_names: Optional[list] = None) -> list:
        """Convert tools to LLM-compatible schema."""
        if tool_names is None:
            tools_to_convert = self.tools.values()
        else:
            tools_to_convert = [self.tools[name] for name in tool_names if name in self.tools]

        return [tool.to_llm_schema() for tool in tools_to_convert]

    def clear(self) -> None:
        """Clear all tools."""
        self.tools = {}


class SandboxedToolkit:
    """
    A collection of sandboxed tools for a session.

    Wraps multiple tools with the same execution context.
    """

    def __init__(
        self,
        tools: list[BaseTool],
        context: WebExecutionContext,
    ):
        """
        Initialize the toolkit.

        Args:
            tools: List of tools to wrap
            context: Web execution context
        """
        self.context = context
        self._tools: Dict[str, SandboxedToolWrapper] = {}
        self._registry = SandboxedToolRegistry()

        for tool in tools:
            wrapped = SandboxedToolWrapper(tool, context)
            self._tools[tool.name] = wrapped
            self._registry.register(wrapped)

    def get(self, name: str) -> Optional[SandboxedToolWrapper]:
        """Get a sandboxed tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[str]:
        """List all tool names."""
        return list(self._tools.keys())

    def get_all(self) -> list[SandboxedToolWrapper]:
        """Get all sandboxed tools."""
        return list(self._tools.values())

    def get_registry(self) -> SandboxedToolRegistry:
        """Get the sandboxed tool registry for RuntimeExecutor."""
        return self._registry

    async def execute(self, tool_name: str, **kwargs) -> ToolResult:
        """
        Execute a tool by name.

        Args:
            tool_name: Name of the tool
            **kwargs: Tool parameters

        Returns:
            ToolResult
        """
        tool = self.get(tool_name)
        if not tool:
            return ToolResult(error=f"Tool '{tool_name}' not found")

        return await tool.execute(**kwargs)
