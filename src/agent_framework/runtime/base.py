"""
Base runtime interface and abstractions.

This module defines the core ToolRuntime interface that all runtime
implementations must follow.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict

from agent_framework.runtime.context import ExecutionContext
from agent_framework.runtime.result import ToolResult


class ToolRuntime(ABC):
    """
    Base interface for tool execution runtimes.
    
    All runtime implementations (Local, Container, MCP, Remote) must
    implement this interface to provide a consistent execution API.
    """
    
    @abstractmethod
    async def execute(
        self,
        tool: "BaseTool",
        params: Dict[str, Any],
        context: ExecutionContext,
    ) -> ToolResult:
        """
        Execute a tool with given parameters in this runtime.
        
        Args:
            tool: The tool to execute
            params: Parameters to pass to the tool
            context: Execution context with timeout, resource limits, etc.
            
        Returns:
            ToolResult containing the execution outcome
            
        Raises:
            TimeoutError: If execution exceeds timeout
            ResourceLimitError: If resource limits are exceeded
            SecurityViolation: If security policy is violated
            RuntimeError: For other runtime-specific errors
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if the runtime is healthy and ready to execute tools.
        
        Returns:
            True if runtime is healthy, False otherwise
        """
        pass
    
    @abstractmethod
    async def cleanup(self) -> None:
        """
        Cleanup runtime resources.
        
        This should be called when the runtime is no longer needed.
        Implementations should clean up any resources like:
        - Running processes
        - Docker containers
        - Network connections
        - Temporary files
        """
        pass
    
    def __repr__(self) -> str:
        """String representation of the runtime."""
        return f"{self.__class__.__name__}()"
