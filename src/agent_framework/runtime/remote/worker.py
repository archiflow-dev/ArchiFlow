"""
Worker node data structures.

This module defines the WorkerNode dataclass and related types
for remote execution.
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class WorkerStatus(Enum):
    """Status of a worker node."""
    AVAILABLE = "available"
    BUSY = "busy"
    OFFLINE = "offline"
    DRAINING = "draining"  # Accepting no new work, finishing existing


@dataclass
class WorkerNode:
    """
    Represents a remote worker node.
    
    Workers execute tools on behalf of the runtime system.
    """
    
    id: str
    """Unique identifier for this worker."""
    
    host: str
    """Hostname or IP address."""
    
    port: int
    """Port number for HTTP API."""
    
    capabilities: List[str] = field(default_factory=list)
    """List of capabilities (e.g., 'gpu', 'high-memory')."""
    
    max_concurrent: int = 5
    """Maximum concurrent tool executions."""
    
    status: WorkerStatus = WorkerStatus.AVAILABLE
    """Current status of the worker."""
    
    current_load: int = 0
    """Number of currently executing tools."""
    
    last_heartbeat: float = field(default_factory=time.time)
    """Timestamp of last heartbeat."""
    
    total_executions: int = 0
    """Total number of tools executed."""
    
    failed_executions: int = 0
    """Number of failed executions."""
    
    @property
    def endpoint(self) -> str:
        """Get the HTTP endpoint URL."""
        return f"http://{self.host}:{self.port}"
    
    @property
    def is_available(self) -> bool:
        """Check if worker is available for new work."""
        return (
            self.status == WorkerStatus.AVAILABLE and
            self.current_load < self.max_concurrent
        )
    
    @property
    def load_percentage(self) -> float:
        """Get current load as percentage."""
        if self.max_concurrent == 0:
            return 100.0
        return (self.current_load / self.max_concurrent) * 100.0
    
    def has_capability(self, capability: str) -> bool:
        """
        Check if worker has a specific capability.
        
        Args:
            capability: Capability to check
            
        Returns:
            True if worker has the capability
        """
        return capability in self.capabilities
    
    def has_all_capabilities(self, capabilities: List[str]) -> bool:
        """
        Check if worker has all required capabilities.
        
        Args:
            capabilities: List of required capabilities
            
        Returns:
            True if worker has all capabilities
        """
        return all(cap in self.capabilities for cap in capabilities)
    
    def __repr__(self) -> str:
        """String representation."""
        return (
            f"WorkerNode(id={self.id!r}, endpoint={self.endpoint!r}, "
            f"status={self.status.value}, load={self.current_load}/{self.max_concurrent})"
        )
