"""
Runtime manager for selecting and managing runtime implementations.

This module provides the RuntimeManager class that coordinates
multiple runtime implementations and selects the appropriate one
based on security policies.
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from agent_framework.runtime.base import ToolRuntime
from agent_framework.runtime.context import ExecutionContext
from agent_framework.runtime.exceptions import (
    RuntimeNotFoundError,
    SecurityViolation,
    ToolNotFoundError,
)
from agent_framework.runtime.result import ToolResult
from agent_framework.runtime.security import SecurityPolicy

logger = logging.getLogger(__name__)


class RuntimeManager:
    """
    Manages multiple runtime implementations and selects the appropriate
    runtime for each tool execution based on security policy.
    """
    
    def __init__(self, security_policy: Optional[SecurityPolicy] = None):
        """
        Initialize the runtime manager.
        
        Args:
            security_policy: Security policy for runtime selection.
                           If None, uses default policy.
        """
        self.runtimes: Dict[str, ToolRuntime] = {}
        self.security_policy = security_policy or SecurityPolicy()
        self.last_runtime_used: Optional[str] = None
        
        logger.info("RuntimeManager initialized with policy: %s", self.security_policy.default_runtime)
    
    def register_runtime(self, name: str, runtime: ToolRuntime) -> None:
        """
        Register a runtime implementation.
        
        Args:
            name: Name of the runtime (e.g., 'local', 'container', 'mcp', 'remote')
            runtime: Runtime implementation instance
        """
        self.runtimes[name] = runtime
        logger.info("Registered runtime: %s (%s)", name, runtime.__class__.__name__)
    
    def unregister_runtime(self, name: str) -> None:
        """
        Unregister a runtime implementation.
        
        Args:
            name: Name of the runtime to unregister
        """
        if name in self.runtimes:
            del self.runtimes[name]
            logger.info("Unregistered runtime: %s", name)
    
    def get_runtime(self, tool_name: str) -> ToolRuntime:
        """
        Get the appropriate runtime for a tool based on security policy.
        
        Args:
            tool_name: Name of the tool to execute
            
        Returns:
            Runtime instance to use
            
        Raises:
            RuntimeNotFoundError: If the required runtime is not registered
        """
        # Check if tool is allowed
        if not self.security_policy.is_tool_allowed(tool_name):
            raise SecurityViolation(
                f"Tool '{tool_name}' is blocked by security policy",
                violation_type="blocked_tool"
            )
        
        # Get runtime name from policy
        runtime_name = self.security_policy.get_runtime_for_tool(tool_name)
        
        # Get runtime instance
        if runtime_name not in self.runtimes:
            raise RuntimeNotFoundError(runtime_name)
        
        return self.runtimes[runtime_name]
    
    async def execute_tool(
        self,
        tool: "BaseTool",
        params: Dict[str, Any],
        context: ExecutionContext,
    ) -> ToolResult:
        """
        Execute a tool using the appropriate runtime.
        
        Args:
            tool: Tool to execute
            params: Parameters for the tool
            context: Execution context
            
        Returns:
            ToolResult from the execution
            
        Raises:
            RuntimeNotFoundError: If required runtime not found
            ToolNotFoundError: If tool is None
            Various runtime-specific exceptions
        """
        if tool is None:
            raise ToolNotFoundError("None")
        
        tool_name = tool.name if hasattr(tool, 'name') else str(tool)
        
        # Get appropriate runtime
        runtime = self.get_runtime(tool_name)
        self.last_runtime_used = self._get_runtime_name(runtime)
        
        logger.info(
            "Executing tool '%s' using runtime '%s'",
            tool_name,
            self.last_runtime_used
        )
        
        # Apply tool-specific policy overrides if they exist
        context = self._apply_tool_policy(tool_name, context)
        
        # Execute
        try:
            result = await runtime.execute(tool, params, context)
            
            # Add runtime metadata
            result.metadata['runtime'] = self.last_runtime_used
            
            logger.info(
                "Tool '%s' execution %s in %.3fs",
                tool_name,
                "succeeded" if result.success else "failed",
                result.execution_time
            )
            
            return result
            
        except Exception as e:
            logger.error(
                "Tool '%s' execution failed in runtime '%s': %s",
                tool_name,
                self.last_runtime_used,
                str(e),
                exc_info=True
            )
            raise
    
    def _get_runtime_name(self, runtime: ToolRuntime) -> str:
        """Get the name of a runtime instance."""
        for name, rt in self.runtimes.items():
            if rt is runtime:
                return name
        return "unknown"
    
    def _apply_tool_policy(
        self,
        tool_name: str,
        context: ExecutionContext
    ) -> ExecutionContext:
        """
        Apply tool-specific policy overrides to the execution context.
        
        Args:
            tool_name: Name of the tool
            context: Original execution context
            
        Returns:
            Modified execution context with policy overrides applied
        """
        tool_policy = self.security_policy.get_tool_policy(tool_name)
        
        if tool_policy is None:
            return context
        
        # Create modified context
        modified_context = ExecutionContext(
            session_id=context.session_id,
            timeout=tool_policy.max_execution_time or context.timeout,
            max_memory_mb=tool_policy.max_memory_mb or context.max_memory_mb,
            max_cpu_percent=context.max_cpu_percent,
            allowed_network=tool_policy.allow_network if tool_policy.allow_network is not None else context.allowed_network,
            working_directory=context.working_directory,
            environment=context.environment.copy(),
            metadata=context.metadata.copy(),
        )
        
        return modified_context
    
    async def health_check_all(self) -> Dict[str, bool]:
        """
        Check health of all registered runtimes.
        
        Returns:
            Dictionary mapping runtime names to health status
        """
        health_status = {}
        
        for name, runtime in self.runtimes.items():
            try:
                is_healthy = await runtime.health_check()
                health_status[name] = is_healthy
                logger.debug("Runtime '%s' health: %s", name, is_healthy)
            except Exception as e:
                health_status[name] = False
                logger.warning("Runtime '%s' health check failed: %s", name, str(e))
        
        return health_status
    
    async def cleanup_all(self) -> None:
        """Cleanup all registered runtimes."""
        logger.info("Cleaning up all runtimes")
        
        for name, runtime in self.runtimes.items():
            try:
                await runtime.cleanup()
                logger.info("Cleaned up runtime: %s", name)
            except Exception as e:
                logger.error("Failed to cleanup runtime '%s': %s", name, str(e))
    
    def get_runtime_stats(self) -> Dict[str, Any]:
        """
        Get statistics about registered runtimes.

        Returns:
            Dictionary with runtime statistics
        """
        return {
            'total_runtimes': len(self.runtimes),
            'registered_runtimes': list(self.runtimes.keys()),
            'default_runtime': self.security_policy.default_runtime,
            'last_runtime_used': self.last_runtime_used,
        }

    def create_session_manager(
        self,
        session_id: str,
        workspace_path: Path,
        storage_quota: Optional["StorageQuota"] = None,
        audit_trail: Optional["AuditTrail"] = None,
        sandbox_mode: str = "strict",
    ) -> "SessionRuntimeManager":
        """
        Create a session-scoped runtime manager.

        The session manager has its own SandboxRuntime (with workspace)
        but delegates to this RuntimeManager for shared runtimes.

        Args:
            session_id: Session identifier
            workspace_path: Session workspace directory (must exist)
            storage_quota: Optional storage quota enforcement
            audit_trail: Optional audit logging
            sandbox_mode: Sandbox enforcement level (strict, permissive, disabled)

        Returns:
            SessionRuntimeManager for this session
        """
        # Import here to avoid circular dependency
        from .session_manager import SessionRuntimeManager

        return SessionRuntimeManager(
            session_id=session_id,
            workspace_path=workspace_path,
            global_manager=self,
            storage_quota=storage_quota,
            audit_trail=audit_trail,
            sandbox_mode=sandbox_mode,
        )
