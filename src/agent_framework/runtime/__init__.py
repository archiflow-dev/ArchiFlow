"""
Runtime system for executing tools in different environments.

This package provides a pluggable runtime system that supports:
- Local execution (current process or subprocess)
- Sandbox execution (with workspace isolation)
- MCP server integration
- Remote execution (distributed workers)
- Session-scoped runtime managers
"""

from .base import ToolRuntime
from .context import ExecutionContext
from .result import ToolResult
from .exceptions import (
    RuntimeException,
    TimeoutError,
    ResourceLimitError,
    SecurityViolation,
)
from .security import SecurityPolicy
from .manager import RuntimeManager
from .local import LocalRuntime

# New sandbox components
from .sandbox import SandboxRuntime, SandboxConfig, SandboxMode
from .session_manager import SessionRuntimeManager
from .validation.path_validator import PathValidator, PathValidationError
from .validation.command_validator import CommandValidator, CommandValidationError

__all__ = [
    # Core
    "ToolRuntime",
    "ExecutionContext",
    "ToolResult",
    # Exceptions
    "RuntimeException",
    "TimeoutError",
    "ResourceLimitError",
    "SecurityViolation",
    # Security
    "SecurityPolicy",
    # Runtimes
    "LocalRuntime",
    "SandboxRuntime",
    "SessionRuntimeManager",
    # Managers
    "RuntimeManager",
    # Config
    "SandboxConfig",
    "SandboxMode",
    # Validation
    "PathValidator",
    "PathValidationError",
    "CommandValidator",
    "CommandValidationError",
]
