"""
Message and QueueConfig dataclasses for the message queue system.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
import time
import uuid


@dataclass
class Message:
    """
    Represents a single message/task in the queue system.
    
    Attributes:
        id: Unique message identifier (UUID)
        topic: Topic/queue name for routing
        payload: Message data (any JSON-serializable object)
        timestamp: Creation timestamp (Unix time)
        retry_count: Number of retry attempts (default: 0)
        max_retries: Maximum retry attempts before moving to DLQ (default: 3)
        error: Last error message if processing failed (default: None)
        metadata: Optional headers/properties (default: empty dict)
    """
    id: str
    topic: str
    payload: Any
    timestamp: float
    retry_count: int = 0
    max_retries: int = 3
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @staticmethod
    def create(topic: str, payload: Any, max_retries: int = 3, 
               metadata: Optional[Dict[str, Any]] = None) -> 'Message':
        """
        Create a new message with auto-generated ID and timestamp.
        
        Args:
            topic: Topic/queue name
            payload: Message data
            max_retries: Maximum retry attempts (default: 3)
            metadata: Optional metadata dict
            
        Returns:
            New Message instance
        """
        return Message(
            id=str(uuid.uuid4()),
            topic=topic,
            payload=payload,
            timestamp=time.time(),
            retry_count=0,
            max_retries=max_retries,
            error=None,
            metadata=metadata or {}
        )


@dataclass
class QueueConfig:
    """
    Configuration for a task queue.
    
    Attributes:
        name: Queue name
        max_retries: Maximum retry attempts for failed tasks (default: 3)
        dlq_enabled: Whether Dead Letter Queue is enabled (default: True)
    """
    name: str
    max_retries: int = 3
    dlq_enabled: bool = True
