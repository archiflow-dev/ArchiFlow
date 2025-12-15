"""
Execution context for tool execution.

This module defines the ExecutionContext dataclass that carries
metadata and constraints for tool execution.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ExecutionContext:
    """
    Context for tool execution containing metadata and constraints.
    
    This context is passed to runtimes to control how tools are executed,
    including timeouts, resource limits, and environment configuration.
    """
    
    # Required fields
    session_id: str
    """Unique identifier for the session executing this tool."""
    
    # Execution constraints
    timeout: int = 30
    """Maximum execution time in seconds. Default: 30s"""
    
    max_memory_mb: int = 512
    """Maximum memory usage in megabytes. Default: 512MB"""
    
    max_cpu_percent: int = 80
    """Maximum CPU usage percentage. Default: 80%"""
    
    # Network and filesystem
    allowed_network: bool = False
    """Whether network access is allowed. Default: False for security"""
    
    working_directory: Optional[str] = None
    """Working directory for tool execution. None means runtime default."""
    
    # Environment
    environment: Dict[str, str] = field(default_factory=dict)
    """Environment variables to set for tool execution."""
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    """Additional metadata for runtime-specific configuration."""
    
    def __post_init__(self):
        """Validate context after initialization."""
        if self.timeout <= 0:
            raise ValueError("timeout must be positive")
        if self.max_memory_mb <= 0:
            raise ValueError("max_memory_mb must be positive")
        if self.max_cpu_percent <= 0 or self.max_cpu_percent > 100:
            raise ValueError("max_cpu_percent must be between 1 and 100")
    
    def with_timeout(self, timeout: int) -> "ExecutionContext":
        """Create a new context with a different timeout."""
        return ExecutionContext(
            session_id=self.session_id,
            timeout=timeout,
            max_memory_mb=self.max_memory_mb,
            max_cpu_percent=self.max_cpu_percent,
            allowed_network=self.allowed_network,
            working_directory=self.working_directory,
            environment=self.environment.copy(),
            metadata=self.metadata.copy(),
        )
    
    def with_network(self, allowed: bool) -> "ExecutionContext":
        """Create a new context with different network access."""
        return ExecutionContext(
            session_id=self.session_id,
            timeout=self.timeout,
            max_memory_mb=self.max_memory_mb,
            max_cpu_percent=self.max_cpu_percent,
            allowed_network=allowed,
            working_directory=self.working_directory,
            environment=self.environment.copy(),
            metadata=self.metadata.copy(),
        )
