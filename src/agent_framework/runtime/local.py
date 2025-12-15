"""
Local runtime for executing tools in the current process.

This module provides the LocalRuntime implementation that executes
tools directly in the current Python process with resource monitoring
and timeout enforcement.
"""

import asyncio
import logging
import psutil
import time
from typing import Any, Dict, Optional

from agent_framework.runtime.base import ToolRuntime
from agent_framework.runtime.context import ExecutionContext
from agent_framework.runtime.exceptions import (
    ExecutionError,
    ResourceLimitError,
    TimeoutError as RuntimeTimeoutError,
)
from agent_framework.runtime.result import ToolResult

logger = logging.getLogger(__name__)


class LocalRuntime(ToolRuntime):
    """
    Runtime for executing tools in the current process.
    
    Features:
    - Direct tool invocation (async or sync)
    - Timeout enforcement
    - Memory monitoring
    - Execution time tracking
    - Resource limit enforcement
    """
    
    def __init__(
        self,
        enable_resource_monitoring: bool = True,
        monitoring_interval: float = 0.5,
    ):
        """
        Initialize the local runtime.
        
        Args:
            enable_resource_monitoring: Whether to monitor resource usage
            monitoring_interval: How often to check resources (seconds)
        """
        self.enable_resource_monitoring = enable_resource_monitoring
        self.monitoring_interval = monitoring_interval
        self._process = psutil.Process()
        
        logger.info(
            "LocalRuntime initialized (resource_monitoring=%s)",
            enable_resource_monitoring
        )
    
    async def execute(
        self,
        tool: "BaseTool",
        params: Dict[str, Any],
        context: ExecutionContext,
    ) -> ToolResult:
        """
        Execute a tool in the local process.
        
        Args:
            tool: Tool to execute
            params: Parameters for the tool
            context: Execution context with timeout and limits
            
        Returns:
            ToolResult with execution outcome
            
        Raises:
            TimeoutError: If execution exceeds timeout
            ResourceLimitError: If resource limits exceeded
            ExecutionError: If tool execution fails
        """
        tool_name = tool.name if hasattr(tool, 'name') else str(tool)
        
        logger.info(
            "Executing tool '%s' locally (timeout=%ds, max_memory=%dMB)",
            tool_name,
            context.timeout,
            context.max_memory_mb
        )
        
        start_time = time.time()
        
        # Start resource monitoring if enabled
        monitor_task = None
        if self.enable_resource_monitoring:
            monitor_task = asyncio.create_task(
                self._monitor_resources(context, tool_name)
            )
        
        try:
            # Execute with timeout
            result = await asyncio.wait_for(
                self._execute_tool(tool, params, context),
                timeout=context.timeout
            )
            
            execution_time = time.time() - start_time
            
            logger.info(
                "Tool '%s' completed successfully in %.3fs",
                tool_name,
                execution_time
            )
            
            return ToolResult.success_result(
                output=str(result),
                execution_time=execution_time,
                runtime="local"
            )
            
        except asyncio.TimeoutError:
            execution_time = time.time() - start_time
            error_msg = (
                f"Tool '{tool_name}' exceeded timeout of {context.timeout}s "
                f"(ran for {execution_time:.1f}s)"
            )
            
            logger.warning(error_msg)
            
            raise RuntimeTimeoutError(error_msg, timeout=context.timeout)
            
        except ResourceLimitError:
            # Re-raise resource limit errors
            raise
            
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"Tool '{tool_name}' execution failed: {str(e)}"
            
            logger.error(error_msg, exc_info=True)
            
            return ToolResult.error_result(
                error=error_msg,
                execution_time=execution_time,
                runtime="local",
                exception_type=type(e).__name__
            )
            
        finally:
            # Stop resource monitoring
            if monitor_task:
                monitor_task.cancel()
                try:
                    await monitor_task
                except asyncio.CancelledError:
                    pass
    
    async def _execute_tool(
        self,
        tool: "BaseTool",
        params: Dict[str, Any],
        context: ExecutionContext,
    ) -> Any:
        """
        Execute the tool (internal method).
        
        Args:
            tool: Tool to execute
            params: Tool parameters
            context: Execution context
            
        Returns:
            Tool execution result
        """
        # Check if tool has execute method
        if not hasattr(tool, 'execute'):
            raise ExecutionError(f"Tool {tool} does not have execute method")
        # Call tool's execute method
        execute_method = getattr(tool, 'execute')
        # Check if it's async
        if asyncio.iscoroutinefunction(execute_method):
            result = await execute_method(**params)
        else:
            # Run sync function in executor to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: execute_method(**params)
            )
        
        return result
    
    async def _monitor_resources(
        self,
        context: ExecutionContext,
        tool_name: str,
    ) -> None:
        """
        Monitor resource usage during execution.
        
        Args:
            context: Execution context with limits
            tool_name: Name of the tool being executed
            
        Raises:
            ResourceLimitError: If limits are exceeded
        """
        try:
            while True:
                await asyncio.sleep(self.monitoring_interval)
                
                # Check memory usage
                memory_info = self._process.memory_info()
                memory_mb = memory_info.rss / (1024 * 1024)
                
                if memory_mb > context.max_memory_mb:
                    error_msg = (
                        f"Tool '{tool_name}' exceeded memory limit: "
                        f"{memory_mb:.1f}MB > {context.max_memory_mb}MB"
                    )
                    
                    logger.warning(error_msg)
                    
                    raise ResourceLimitError(
                        error_msg,
                        resource_type="memory",
                        limit=context.max_memory_mb,
                        actual=memory_mb
                    )
                
                # Log resource usage periodically
                if logger.isEnabledFor(logging.DEBUG):
                    cpu_percent = self._process.cpu_percent()
                    logger.debug(
                        "Tool '%s' resources: memory=%.1fMB, cpu=%.1f%%",
                        tool_name,
                        memory_mb,
                        cpu_percent
                    )
                    
        except asyncio.CancelledError:
            # Monitoring was cancelled (normal)
            pass
    
    async def health_check(self) -> bool:
        """
        Check if the local runtime is healthy.
        
        Returns:
            True (local runtime is always available)
        """
        return True
    
    async def cleanup(self) -> None:
        """
        Cleanup local runtime resources.
        
        For local runtime, there's nothing to cleanup.
        """
        logger.info("LocalRuntime cleanup (no-op)")
        pass
    
    def get_current_memory_mb(self) -> float:
        """
        Get current memory usage in MB.
        
        Returns:
            Current memory usage in megabytes
        """
        memory_info = self._process.memory_info()
        return memory_info.rss / (1024 * 1024)
    
    def get_current_cpu_percent(self) -> float:
        """
        Get current CPU usage percentage.
        
        Returns:
            CPU usage percentage
        """
        return self._process.cpu_percent(interval=0.1)
