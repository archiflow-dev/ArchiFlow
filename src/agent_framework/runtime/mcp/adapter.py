"""
MCP tool adapter and registry.

This module provides the MCPToolAdapter class that adapts MCP tools
to the BaseTool interface, and MCPToolRegistry for managing discovered tools.
"""

import logging
from typing import Any, Dict, List, Optional

from agent_framework.runtime.result import ToolResult

logger = logging.getLogger(__name__)


class MCPToolAdapter:
    """
    Adapter to use MCP tools as BaseTool.
    
    Wraps an MCP tool and provides the BaseTool interface for
    seamless integration with the runtime system.
    """
    
    def __init__(
        self,
        server_name: str,
        tool_name: str,
        description: str,
        input_schema: Dict[str, Any],
        session: "MCPSession"
    ):
        """
        Initialize the tool adapter.
        
        Args:
            server_name: Name of the MCP server providing this tool
            tool_name: Original tool name from MCP server
            description: Tool description
            input_schema: JSON schema for tool parameters
            session: MCP session for executing the tool
        """
        self.server_name = server_name
        self.name = f"{server_name}.{tool_name}"
        self.description = description
        self.input_schema = input_schema
        self.session = session
        self._mcp_tool_name = tool_name
    
    async def execute(self, **params) -> ToolResult:
        """
        Execute the MCP tool (BaseTool interface).
        
        Args:
            **params: Tool parameters
            
        Returns:
            ToolResult from execution
        """
        result = await self.execute_mcp(params)
        
        return ToolResult(
            success=not result.isError,
            output=result.content[0].text if result.content else "",
            error=result.content[0].text if result.isError else None,
            metadata={
                'mcp_server': self.server_name,
                'mcp_tool': self._mcp_tool_name
            }
        )
    
    async def execute_mcp(self, params: Dict[str, Any]) -> "CallToolResult":
        """
        Execute tool using MCP protocol.
        
        Args:
            params: Tool parameters
            
        Returns:
            CallToolResult from MCP server
        """
        # Validate parameters
        self._validate_params(params)
        
        # Call tool via MCP
        result = await self.session.call_tool(
            name=self._mcp_tool_name,
            arguments=params
        )
        
        return result
    
    def _validate_params(self, params: Dict[str, Any]) -> None:
        """
        Validate parameters against input schema.
        
        Args:
            params: Parameters to validate
            
        Raises:
            ValueError: If required parameters are missing
        """
        if 'required' in self.input_schema:
            required_fields = self.input_schema['required']
            for field in required_fields:
                if field not in params:
                    raise ValueError(f"Missing required parameter: {field}")
    
    def get_schema(self) -> Dict[str, Any]:
        """
        Get tool schema for LLM.
        
        Returns:
            Schema dictionary with name, description, and parameters
        """
        return {
            'name': self.name,
            'description': self.description,
            'parameters': self.input_schema
        }
    
    def __repr__(self) -> str:
        """String representation."""
        return f"MCPToolAdapter(name={self.name!r}, server={self.server_name!r})"


class MCPToolRegistry:
    """
    Registry for MCP tools.
    
    Manages discovered tools from all MCP servers.
    """
    
    def __init__(self):
        """Initialize the registry."""
        self.tools: Dict[str, MCPToolAdapter] = {}
        self.tools_by_server: Dict[str, List[MCPToolAdapter]] = {}
        
        logger.info("MCPToolRegistry initialized")
    
    def register(self, tool: MCPToolAdapter) -> None:
        """
        Register an MCP tool.
        
        Args:
            tool: Tool adapter to register
        """
        self.tools[tool.name] = tool
        
        if tool.server_name not in self.tools_by_server:
            self.tools_by_server[tool.server_name] = []
        
        self.tools_by_server[tool.server_name].append(tool)
        
        logger.debug(f"Registered MCP tool: {tool.name}")
    
    def get(self, tool_name: str) -> Optional[MCPToolAdapter]:
        """
        Get tool by name.
        
        Args:
            tool_name: Fully qualified tool name (server.tool)
            
        Returns:
            Tool adapter if found, None otherwise
        """
        return self.tools.get(tool_name)
    
    def list_all(self) -> List[MCPToolAdapter]:
        """
        List all registered tools.
        
        Returns:
            List of all tool adapters
        """
        return list(self.tools.values())
    
    def list_by_server(self, server_name: str) -> List[MCPToolAdapter]:
        """
        List tools from specific server.
        
        Args:
            server_name: Name of the server
            
        Returns:
            List of tools from that server
        """
        return self.tools_by_server.get(server_name, [])
    
    def get_schemas(self) -> List[Dict[str, Any]]:
        """
        Get schemas for all tools (for LLM).
        
        Returns:
            List of tool schemas
        """
        return [tool.get_schema() for tool in self.tools.values()]
    
    def clear(self) -> None:
        """Clear all registered tools."""
        self.tools.clear()
        self.tools_by_server.clear()
        logger.info("Cleared all tools from registry")
    
    def unregister_server_tools(self, server_name: str) -> None:
        """
        Unregister all tools from a specific server.
        
        Args:
            server_name: Name of the server
        """
        if server_name in self.tools_by_server:
            tools = self.tools_by_server[server_name]
            for tool in tools:
                if tool.name in self.tools:
                    del self.tools[tool.name]
            del self.tools_by_server[server_name]
            
            logger.info(f"Unregistered {len(tools)} tools from server: {server_name}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get registry statistics.
        
        Returns:
            Dictionary with statistics
        """
        return {
            'total_tools': len(self.tools),
            'servers': list(self.tools_by_server.keys()),
            'tools_per_server': {
                server: len(tools)
                for server, tools in self.tools_by_server.items()
            }
        }
