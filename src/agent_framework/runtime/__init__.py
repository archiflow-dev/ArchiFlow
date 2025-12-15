"""
Runtime system for executing tools in different environments.

This package provides a pluggable runtime system that supports:
- Local execution (current process or subprocess)
- Container execution (Docker)
- MCP server integration
- Remote execution (distributed workers)
"""

from agent_framework.runtime.base import ToolRuntime
from agent_framework.runtime.context import ExecutionContext
from agent_framework.runtime.result import ToolResult
from agent_framework.runtime.exceptions import (
    RuntimeException,
    TimeoutError,
    ResourceLimitError,
    SecurityViolation,
)
from agent_framework.runtime.local import LocalRuntime

__all__ = [
    "ToolRuntime",
    "ExecutionContext",
    "ToolResult",
    "RuntimeException",
    "TimeoutError",
    "ResourceLimitError",
    "SecurityViolation",
    "LocalRuntime",
]
