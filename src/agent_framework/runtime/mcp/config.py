"""
Configuration for MCP servers.

This module defines the configuration dataclass for MCP server connections.
"""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class MCPServerConfig:
    """
    Configuration for an MCP server.
    
    Defines how to connect to and start an MCP server.
    """
    
    name: str
    """Unique name for this server."""
    
    command: str
    """Command to start the server (e.g., 'npx', 'python', executable path)."""
    
    args: List[str] = field(default_factory=list)
    """Arguments to pass to the command."""
    
    env: Dict[str, str] = field(default_factory=dict)
    """Environment variables to set for the server process."""
    
    transport: str = "stdio"
    """Transport protocol: 'stdio', 'sse', or 'http'."""
    
    def __post_init__(self):
        """Validate configuration."""
        if not self.name:
            raise ValueError("Server name cannot be empty")
        if not self.command:
            raise ValueError("Server command cannot be empty")
        if self.transport not in ("stdio", "sse", "http"):
            raise ValueError(f"Invalid transport: {self.transport}")
    
    def __repr__(self) -> str:
        """String representation."""
        return f"MCPServerConfig(name={self.name!r}, command={self.command!r}, transport={self.transport!r})"
