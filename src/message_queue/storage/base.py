"""
Base interface for storage backends.
"""
from abc import ABC, abstractmethod
from typing import Optional, List, Any
from ..message import Message

class StorageBackend(ABC):
    """
    Abstract base class for storage backends.
    Defines the interface for queue and message operations.
    """
    
    @abstractmethod
    def initialize(self) -> None:
        """Setup connections, tables, directories, etc."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close connections and cleanup resources."""
        pass

    @abstractmethod
    def create_queue(self, name: str) -> None:
        """
        Create a new queue.
        Raises QueueAlreadyExistsError if queue exists.
        """
        pass

    @abstractmethod
    def delete_queue(self, name: str) -> None:
        """
        Delete a queue and all its messages.
        Raises QueueNotFoundError if queue does not exist.
        """
        pass

    @abstractmethod
    def enqueue(self, queue_name: str, message: Message) -> None:
        """
        Add a message to the queue.
        Raises QueueNotFoundError if queue does not exist.
        """
        pass

    @abstractmethod
    def dequeue(self, queue_name: str, timeout: float = None) -> Optional[Message]:
        """
        Retrieve a message from the queue.
        Should block up to `timeout` seconds.
        Returns None if timeout reached or queue empty.
        Raises QueueNotFoundError if queue does not exist.
        """
        pass

    @abstractmethod
    def ack(self, queue_name: str, message_id: str) -> None:
        """
        Acknowledge successful processing. 
        For persistent stores, this deletes the message.
        """
        pass

    @abstractmethod
    def nack(self, queue_name: str, message_id: str) -> None:
        """
        Negative acknowledgement (processing failed).
        Should increment retry count and schedule for retry or move to DLQ.
        """
        pass

    # --- DLQ Operations ---

    @abstractmethod
    def get_dlq_messages(self, queue_name: str) -> List[Message]:
        """
        List messages in the DLQ.
        Raises QueueNotFoundError if queue does not exist.
        """
        pass

    @abstractmethod
    def requeue_from_dlq(self, queue_name: str, message_id: str) -> None:
        """
        Move message from DLQ back to main queue.
        Raises QueueNotFoundError if queue does not exist.
        Raises MessageNotFoundError if message not in DLQ.
        """
        pass

    @abstractmethod
    def delete_dlq_message(self, queue_name: str, message_id: str) -> None:
        """
        Permanently delete a message from DLQ.
        Raises QueueNotFoundError if queue does not exist.
        Raises MessageNotFoundError if message not in DLQ.
        """
        pass
        
    @abstractmethod
    def move_to_dlq(self, queue_name: str, message: Message) -> None:
        """
        Move a message to the DLQ (e.g. after max retries).
        Raises QueueNotFoundError if queue does not exist.
        """
        pass

    # --- Metrics Support ---
    
    @abstractmethod
    def get_queue_depth(self, queue_name: str) -> int:
        """
        Get current number of pending messages.
        Raises QueueNotFoundError if queue does not exist.
        """
        pass
    
    @abstractmethod
    def get_dlq_depth(self, queue_name: str) -> int:
        """
        Get current number of messages in DLQ.
        Raises QueueNotFoundError if queue does not exist.
        """
        pass
