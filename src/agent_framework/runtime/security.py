"""
Security policy for tool execution.

This module defines the SecurityPolicy dataclass that specifies
execution constraints and permissions.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class SecurityPolicy:
    """
    Security policy for tool execution.
    
    Defines which runtime to use for which tools, resource limits,
    and security constraints.
    """
    
    # Runtime selection
    default_runtime: str = "local"
    """Default runtime to use if no specific mapping exists."""
    
    tool_runtime_map: Dict[str, str] = field(default_factory=dict)
    """Mapping of tool names to specific runtimes. Example: {'bash': 'container'}"""
    
    # Resource limits
    max_execution_time: int = 60
    """Maximum execution time in seconds for any tool."""
    
    max_memory_mb: int = 1024
    """Maximum memory in MB for any tool."""
    
    max_cpu_percent: int = 80
    """Maximum CPU usage percentage for any tool."""
    
    # Permissions
    allow_network: bool = False
    """Whether network access is allowed by default."""
    
    allow_filesystem_write: bool = True
    """Whether filesystem write access is allowed."""
    
    allowed_paths: List[str] = field(default_factory=list)
    """List of allowed filesystem paths. Empty means all paths allowed."""
    
    blocked_commands: List[str] = field(default_factory=list)
    """List of blocked commands/tools."""
    
    # Tool-specific overrides
    tool_specific_policies: Dict[str, "ToolPolicy"] = field(default_factory=dict)
    """Tool-specific policy overrides."""
    
    def get_runtime_for_tool(self, tool_name: str) -> str:
        """
        Get the runtime to use for a specific tool.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            Runtime name to use
        """
        return self.tool_runtime_map.get(tool_name, self.default_runtime)
    
    def is_tool_allowed(self, tool_name: str) -> bool:
        """
        Check if a tool is allowed to execute.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            True if tool is allowed, False if blocked
        """
        return tool_name not in self.blocked_commands
    
    def get_tool_policy(self, tool_name: str) -> Optional["ToolPolicy"]:
        """
        Get tool-specific policy if it exists.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            ToolPolicy if exists, None otherwise
        """
        return self.tool_specific_policies.get(tool_name)


@dataclass
class ToolPolicy:
    """
    Policy for a specific tool.
    
    Allows overriding the default security policy for individual tools.
    """
    
    runtime: Optional[str] = None
    """Override runtime for this tool."""
    
    max_execution_time: Optional[int] = None
    """Override max execution time."""
    
    max_memory_mb: Optional[int] = None
    """Override max memory."""
    
    allow_network: Optional[bool] = None
    """Override network permission."""
    
    allowed_paths: Optional[List[str]] = None
    """Override allowed paths."""
