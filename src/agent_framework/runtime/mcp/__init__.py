"""
MCP runtime package for integrating with MCP servers.

This package provides integration with Model Context Protocol (MCP) servers,
allowing the agent to discover and execute tools from external MCP-compliant services.
"""

from agent_framework.runtime.mcp.runtime import MCPRuntime
from agent_framework.runtime.mcp.config import MCPServerConfig

__all__ = [
    "MCPRuntime",
    "MCPServerConfig",
]
