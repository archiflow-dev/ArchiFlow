"""
In-memory storage backend implementation.
"""
import queue
import threading
from typing import Dict, List, Optional
from .base import StorageBackend
from ..message import Message
from ..exceptions import QueueNotFoundError, QueueAlreadyExistsError, MessageNotFoundError

class InMemoryBackend(StorageBackend):
    """
    In-memory implementation using Python's queue.Queue.
    """
    
    def __init__(self):
        self._queues: Dict[str, queue.Queue] = {}
        self._dlqs: Dict[str, List[Message]] = {}
        self._processing: Dict[str, Dict[str, Message]] = {} # queue_name -> {msg_id -> Message}
        self._lock = threading.RLock()

    def initialize(self) -> None:
        pass

    def close(self) -> None:
        pass

    def create_queue(self, name: str) -> None:
        with self._lock:
            if name in self._queues:
                raise QueueAlreadyExistsError(f"Queue '{name}' already exists")
            self._queues[name] = queue.Queue()
            self._dlqs[name] = []
            self._processing[name] = {}

    def delete_queue(self, name: str) -> None:
        with self._lock:
            if name not in self._queues:
                raise QueueNotFoundError(f"Queue '{name}' does not exist")
            del self._queues[name]
            del self._dlqs[name]
            del self._processing[name]

    def enqueue(self, queue_name: str, message: Message) -> None:
        if queue_name not in self._queues:
            raise QueueNotFoundError(f"Queue '{queue_name}' does not exist")
        self._queues[queue_name].put(message)

    def dequeue(self, queue_name: str, timeout: float = None) -> Optional[Message]:
        if queue_name not in self._queues:
            raise QueueNotFoundError(f"Queue '{queue_name}' does not exist")
        
        try:
            message = self._queues[queue_name].get(timeout=timeout)
            # Track as processing
            with self._lock:
                self._processing[queue_name][message.id] = message
            return message
        except queue.Empty:
            return None

    def ack(self, queue_name: str, message_id: str) -> None:
        with self._lock:
            if queue_name not in self._processing:
                 # If queue doesn't exist, maybe it was deleted? Just ignore or raise?
                 # Raising is safer.
                 raise QueueNotFoundError(f"Queue '{queue_name}' does not exist")
            
            if message_id in self._processing[queue_name]:
                del self._processing[queue_name][message_id]

    def nack(self, queue_name: str, message_id: str) -> None:
        with self._lock:
            if queue_name not in self._processing:
                raise QueueNotFoundError(f"Queue '{queue_name}' does not exist")
            
            if message_id in self._processing[queue_name]:
                message = self._processing[queue_name].pop(message_id)
                # Re-enqueue
                self._queues[queue_name].put(message)

    # --- DLQ Operations ---

    def get_dlq_messages(self, queue_name: str) -> List[Message]:
        with self._lock:
            if queue_name not in self._dlqs:
                raise QueueNotFoundError(f"Queue '{queue_name}' does not exist")
            return list(self._dlqs[queue_name])

    def requeue_from_dlq(self, queue_name: str, message_id: str) -> None:
        with self._lock:
            if queue_name not in self._dlqs:
                raise QueueNotFoundError(f"Queue '{queue_name}' does not exist")
            
            dlq = self._dlqs[queue_name]
            # Find message
            msg_index = -1
            for i, msg in enumerate(dlq):
                if msg.id == message_id:
                    msg_index = i
                    break
            
            if msg_index == -1:
                raise MessageNotFoundError(f"Message {message_id} not found in DLQ for {queue_name}")
            
            message = dlq.pop(msg_index)
            # Reset retry count? The broker usually handles this logic, but storage just moves it.
            # The broker logic: message.retry_count = 0; message.error = None
            # We should probably let the broker modify the message before calling this, 
            # OR this method just moves it.
            # Since we are just moving, we move it. The Broker should have updated it if needed?
            # Actually, `requeue_from_dlq` in Broker does:
            #   msg.retry_count = 0
            #   msg.error = None
            #   self.enqueue(...)
            # So the Broker will likely NOT call this method on the backend directly if it can just 
            # get the message and enqueue it.
            # BUT, to get the message out of DLQ, it needs `delete_dlq_message` or similar.
            #
            # Let's assume this method moves it from DLQ to Main Queue directly.
            self._queues[queue_name].put(message)

    def delete_dlq_message(self, queue_name: str, message_id: str) -> None:
        with self._lock:
            if queue_name not in self._dlqs:
                raise QueueNotFoundError(f"Queue '{queue_name}' does not exist")
            
            dlq = self._dlqs[queue_name]
            msg_index = -1
            for i, msg in enumerate(dlq):
                if msg.id == message_id:
                    msg_index = i
                    break
            
            if msg_index != -1:
                dlq.pop(msg_index)
            else:
                raise MessageNotFoundError(f"Message {message_id} not found in DLQ for {queue_name}")

    # --- Metrics Support ---
    
    def get_queue_depth(self, queue_name: str) -> int:
        if queue_name not in self._queues:
            raise QueueNotFoundError(f"Queue '{queue_name}' does not exist")
        return self._queues[queue_name].qsize()
    
    def get_dlq_depth(self, queue_name: str) -> int:
        with self._lock:
            if queue_name not in self._dlqs:
                raise QueueNotFoundError(f"Queue '{queue_name}' does not exist")
            return len(self._dlqs[queue_name])
    
    # Additional helper for Broker to put things into DLQ directly (when max retries exceeded)
    def move_to_dlq(self, queue_name: str, message: Message) -> None:
        """
        Move a message to the DLQ.
        This is not in the base interface but useful/needed.
        Actually, the Broker can just `enqueue` to DLQ? No, DLQ is special.
        The interface needs a way to put things in DLQ.
        """
        with self._lock:
            if queue_name not in self._dlqs:
                raise QueueNotFoundError(f"Queue '{queue_name}' does not exist")
            self._dlqs[queue_name].append(message)
