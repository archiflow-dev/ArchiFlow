"""
MCP Runtime for executing tools via MCP servers.

This module provides the MCPRuntime class that integrates with
external MCP servers to discover and execute tools.
"""

import asyncio
import logging
import time
from typing import Any, Dict, List

from agent_framework.runtime.base import ToolRuntime
from agent_framework.runtime.context import ExecutionContext
from agent_framework.runtime.exceptions import ExecutionError
from agent_framework.runtime.mcp.adapter import MCPToolAdapter, MCPToolRegistry
from agent_framework.runtime.mcp.config import MCPServerConfig
from agent_framework.runtime.mcp.server_manager import MCPServerManager
from agent_framework.runtime.result import ToolResult

logger = logging.getLogger(__name__)


class MCPRuntime(ToolRuntime):
    """
    Runtime for executing tools via MCP servers.
    
    Features:
    - Automatic tool discovery from MCP servers
    - Tool execution via MCP protocol
    - Server lifecycle management
    - Retry logic with server restart
    - Tool registry for discovered tools
    """
    
    def __init__(
        self,
        server_configs: List[MCPServerConfig],
        retry_attempts: int = 3,
        retry_delay: float = 1.0
    ):
        """
        Initialize the MCP runtime.
        
        Args:
            server_configs: List of MCP server configurations
            retry_attempts: Number of retry attempts on failure
            retry_delay: Delay between retries in seconds
        """
        self.server_configs = server_configs
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        
        self.server_manager = MCPServerManager()
        self.tool_registry = MCPToolRegistry()
        self._initialized = False
        
        logger.info(
            "MCPRuntime initialized with %d server(s)",
            len(server_configs)
        )
    
    async def initialize(self) -> None:
        """
        Initialize MCP servers and discover tools.
        
        This must be called before executing tools.
        """
        if self._initialized:
            logger.debug("MCPRuntime already initialized")
            return
        
        logger.info("Initializing MCP runtime...")
        
        # Start all configured servers
        for config in self.server_configs:
            try:
                await self.server_manager.start_server(config)
            except Exception as e:
                logger.error(
                    f"Failed to start server {config.name}: {e}",
                    exc_info=True
                )
                # Continue with other servers
        
        # Discover tools from all servers
        await self._discover_tools()
        
        self._initialized = True
        
        logger.info(
            "MCP runtime initialized with %d tool(s) from %d server(s)",
            len(self.tool_registry.tools),
            len(self.server_manager.sessions)
        )
    
    async def _discover_tools(self) -> None:
        """Discover tools from all connected servers."""
        for server_name, session in self.server_manager.sessions.items():
            try:
                # List available tools
                tools_result = await session.list_tools()
                
                logger.info(
                    f"Discovering tools from server: {server_name}"
                )
                
                for tool_info in tools_result.tools:
                    # Create tool adapter
                    adapter = MCPToolAdapter(
                        server_name=server_name,
                        tool_name=tool_info.name,
                        description=tool_info.description,
                        input_schema=tool_info.inputSchema,
                        session=session
                    )
                    
                    # Register tool
                    self.tool_registry.register(adapter)
                
                logger.info(
                    f"Discovered {len(tools_result.tools)} tool(s) from {server_name}"
                )
                
            except Exception as e:
                logger.error(
                    f"Failed to discover tools from {server_name}: {e}",
                    exc_info=True
                )
    
    async def execute(
        self,
        tool: "BaseTool",
        params: Dict[str, Any],
        context: ExecutionContext,
    ) -> ToolResult:
        """
        Execute an MCP tool.
        
        Args:
            tool: Tool to execute (must be MCPToolAdapter)
            params: Tool parameters
            context: Execution context
            
        Returns:
            ToolResult from execution
        """
        if not self._initialized:
            await self.initialize()
        
        # Verify tool is an MCP tool
        if not isinstance(tool, MCPToolAdapter):
            return ToolResult.error_result(
                error=f"Tool {tool} is not an MCP tool",
                runtime="mcp"
            )
        
        tool_name = tool.name
        
        logger.info(
            f"Executing MCP tool '{tool_name}' from server '{tool.server_name}'"
        )
        
        # Execute with retry logic
        for attempt in range(self.retry_attempts):
            try:
                start_time = time.time()
                
                # Execute via MCP with timeout
                result = await asyncio.wait_for(
                    tool.execute_mcp(params),
                    timeout=context.timeout
                )
                
                execution_time = time.time() - start_time
                
                # Convert to ToolResult
                tool_result = ToolResult(
                    success=not result.isError,
                    output=result.content[0].text if result.content else "",
                    error=result.content[0].text if result.isError else None,
                    execution_time=execution_time,
                    metadata={
                        'runtime': 'mcp',
                        'mcp_server': tool.server_name,
                        'mcp_tool': tool._mcp_tool_name,
                        'attempt': attempt + 1
                    }
                )
                
                logger.info(
                    f"MCP tool '{tool_name}' completed in {execution_time:.3f}s "
                    f"(attempt {attempt + 1}/{self.retry_attempts})"
                )
                
                return tool_result
                
            except asyncio.TimeoutError:
                error_msg = (
                    f"MCP tool '{tool_name}' timed out after {context.timeout}s "
                    f"(attempt {attempt + 1}/{self.retry_attempts})"
                )
                logger.warning(error_msg)
                
                if attempt < self.retry_attempts - 1:
                    # Try restarting the server
                    try:
                        await self.server_manager.restart_server(tool.server_name)
                        await asyncio.sleep(self.retry_delay)
                    except Exception as e:
                        logger.error(f"Failed to restart server: {e}")
                else:
                    return ToolResult.error_result(
                        error=error_msg,
                        runtime="mcp"
                    )
                    
            except Exception as e:
                error_msg = f"MCP tool '{tool_name}' failed: {str(e)}"
                logger.error(
                    f"{error_msg} (attempt {attempt + 1}/{self.retry_attempts})",
                    exc_info=True
                )
                
                if attempt < self.retry_attempts - 1:
                    await asyncio.sleep(self.retry_delay * (2 ** attempt))
                else:
                    return ToolResult.error_result(
                        error=error_msg,
                        runtime="mcp",
                        exception_type=type(e).__name__
                    )
        
        # Should not reach here
        return ToolResult.error_result(
            error=f"MCP tool '{tool_name}' failed after {self.retry_attempts} attempts",
            runtime="mcp"
        )
    
    async def health_check(self) -> bool:
        """
        Check if MCP servers are healthy.
        
        Returns:
            True if at least one server is running
        """
        if not self._initialized:
            return False
        
        return self.server_manager.all_servers_healthy()
    
    async def cleanup(self) -> None:
        """Cleanup MCP servers and resources."""
        logger.info("Cleaning up MCP runtime")
        
        await self.server_manager.stop_all_servers()
        self.tool_registry.clear()
        self._initialized = False
        
        logger.info("MCP runtime cleanup complete")
    
    def get_mcp_tools(self) -> List[MCPToolAdapter]:
        """
        Get all available MCP tools.
        
        Returns:
            List of MCP tool adapters
        """
        return self.tool_registry.list_all()
    
    def get_mcp_tool_schemas(self) -> List[Dict[str, Any]]:
        """
        Get schemas for all MCP tools (for LLM).
        
        Returns:
            List of tool schemas
        """
        return self.tool_registry.get_schemas()
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get runtime statistics.
        
        Returns:
            Dictionary with statistics
        """
        return {
            'initialized': self._initialized,
            'servers_configured': len(self.server_configs),
            'servers_running': len(self.server_manager.sessions),
            'tools_discovered': len(self.tool_registry.tools),
            'registry_stats': self.tool_registry.get_stats()
        }
