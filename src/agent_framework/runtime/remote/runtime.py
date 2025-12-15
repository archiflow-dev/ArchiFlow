"""
Remote runtime for executing tools on distributed worker nodes.

This module provides the RemoteRuntime class that distributes
tool execution across remote workers with load balancing and failover.
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

# Note: aiohttp is optional, will use a simplified HTTP client if not available
try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False

from agent_framework.runtime.base import ToolRuntime
from agent_framework.runtime.context import ExecutionContext
from agent_framework.runtime.exceptions import ExecutionError, RuntimeInitializationError
from agent_framework.runtime.remote.pool_manager import WorkerPoolManager
from agent_framework.runtime.remote.worker import WorkerNode
from agent_framework.runtime.result import ToolResult

logger = logging.getLogger(__name__)


class RemoteRuntime(ToolRuntime):
    """
    Runtime for executing tools on remote worker nodes.
    
    Features:
    - Distributed execution across workers
    - Load balancing with multiple strategies
    - Automatic failover on worker failures
    - Retry logic with different workers
    - Health monitoring
    """
    
    def __init__(
        self,
        worker_pool: WorkerPoolManager,
        timeout: int = 60,
        retry_attempts: int = 3
    ):
        """
        Initialize the remote runtime.
        
        Args:
            worker_pool: Worker pool manager
            timeout: Default timeout for HTTP requests
            retry_attempts: Number of retry attempts on failure
        """
        if not HAS_AIOHTTP:
            raise RuntimeInitializationError(
                "aiohttp is required for RemoteRuntime. "
                "Install it with: pip install aiohttp"
            )
        
        self.worker_pool = worker_pool
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.session: Optional[aiohttp.ClientSession] = None
        
        logger.info(
            "RemoteRuntime initialized (timeout=%ds, retries=%d)",
            timeout,
            retry_attempts
        )
    
    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Ensure HTTP session is created."""
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def execute(
        self,
        tool: "BaseTool",
        params: Dict[str, Any],
        context: ExecutionContext,
    ) -> ToolResult:
        """
        Execute a tool on a remote worker.
        
        Args:
            tool: Tool to execute
            params: Tool parameters
            context: Execution context
            
        Returns:
            ToolResult from execution
        """
        tool_name = tool.name if hasattr(tool, 'name') else str(tool)
        
        # Get required capabilities from tool
        required_capabilities = self._get_required_capabilities(tool)
        
        logger.info(
            f"Executing tool '{tool_name}' remotely "
            f"(capabilities: {required_capabilities})"
        )
        
        # Try execution with retries
        excluded_workers: List[str] = []
        
        for attempt in range(self.retry_attempts):
            try:
                # Select worker
                worker = await self.worker_pool.select_worker(
                    required_capabilities=required_capabilities,
                    exclude=excluded_workers
                )
                
                if not worker:
                    return ToolResult.error_result(
                        error=f"No available workers for tool '{tool_name}'",
                        runtime="remote"
                    )
                
                logger.debug(
                    f"Selected worker {worker.id} for '{tool_name}' "
                    f"(attempt {attempt + 1}/{self.retry_attempts})"
                )
                
                # Execute on worker
                try:
                    result = await self._execute_on_worker(
                        worker,
                        tool,
                        params,
                        context
                    )
                    
                    # Success - update worker stats
                    worker.total_executions += 1
                    
                    return result
                    
                finally:
                    # Always release worker
                    await self.worker_pool.release_worker(worker.id)
                
            except Exception as e:
                logger.warning(
                    f"Execution failed on worker {worker.id if worker else 'unknown'}: {e} "
                    f"(attempt {attempt + 1}/{self.retry_attempts})"
                )
                
                # Mark worker as failed
                if worker:
                    await self.worker_pool.mark_worker_failed(worker.id)
                    excluded_workers.append(worker.id)
                
                if attempt < self.retry_attempts - 1:
                    # Retry on different worker
                    continue
                else:
                    # All retries exhausted
                    return ToolResult.error_result(
                        error=f"Execution failed after {self.retry_attempts} attempts: {str(e)}",
                        runtime="remote",
                        exception_type=type(e).__name__
                    )
        
        # Should not reach here
        return ToolResult.error_result(
            error=f"Tool '{tool_name}' failed after {self.retry_attempts} attempts",
            runtime="remote"
        )
    
    async def _execute_on_worker(
        self,
        worker: WorkerNode,
        tool: "BaseTool",
        params: Dict[str, Any],
        context: ExecutionContext
    ) -> ToolResult:
        """
        Execute tool on specific worker.
        
        Args:
            worker: Worker to execute on
            tool: Tool to execute
            params: Tool parameters
            context: Execution context
            
        Returns:
            ToolResult from execution
        """
        session = await self._ensure_session()
        
        tool_name = tool.name if hasattr(tool, 'name') else str(tool)
        
        # Prepare request payload
        payload = {
            'tool_name': tool_name,
            'parameters': params,
            'context': {
                'session_id': context.session_id,
                'timeout': context.timeout or self.timeout,
                'max_memory_mb': context.max_memory_mb,
                'max_cpu_percent': context.max_cpu_percent,
                'allowed_network': context.allowed_network,
                'working_directory': context.working_directory,
                'environment': context.environment
            }
        }
        
        start_time = time.time()
        
        # Send execution request
        try:
            async with session.post(
                f"{worker.endpoint}/execute",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            ) as response:
                
                if response.status != 200:
                    error_text = await response.text()
                    raise ExecutionError(
                        f"Worker returned status {response.status}: {error_text}"
                    )
                
                result_data = await response.json()
                
                execution_time = time.time() - start_time
                
                return ToolResult(
                    success=result_data['success'],
                    output=result_data.get('output'),
                    error=result_data.get('error'),
                    execution_time=execution_time,
                    metadata={
                        'runtime': 'remote',
                        'worker_id': worker.id,
                        'worker_endpoint': worker.endpoint
                    }
                )
                
        except asyncio.TimeoutError:
            raise ExecutionError(
                f"Worker {worker.id} timed out after {self.timeout}s"
            )
        except aiohttp.ClientError as e:
            raise ExecutionError(
                f"HTTP error communicating with worker {worker.id}: {str(e)}"
            )
    
    def _get_required_capabilities(self, tool: "BaseTool") -> List[str]:
        """
        Determine required worker capabilities for tool.
        
        Args:
            tool: Tool to check
            
        Returns:
            List of required capabilities
        """
        capabilities = []
        
        # Check tool metadata for requirements
        if hasattr(tool, 'requires_gpu') and tool.requires_gpu:
            capabilities.append('gpu')
        
        if hasattr(tool, 'requires_high_memory') and tool.requires_high_memory:
            capabilities.append('high-memory')
        
        if hasattr(tool, 'required_capabilities'):
            capabilities.extend(tool.required_capabilities)
        
        return capabilities
    
    async def health_check(self) -> bool:
        """
        Check if any workers are available.
        
        Returns:
            True if at least one worker is available
        """
        return await self.worker_pool.has_available_workers()
    
    async def cleanup(self) -> None:
        """Cleanup resources."""
        if self.session:
            await self.session.close()
            self.session = None
        
        logger.info("RemoteRuntime cleanup complete")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get runtime statistics.
        
        Returns:
            Dictionary with statistics
        """
        return {
            'runtime': 'remote',
            'timeout': self.timeout,
            'retry_attempts': self.retry_attempts,
            'worker_pool': self.worker_pool.get_worker_stats()
        }
