"""
FileBackend - File system based storage backend.
"""
import os
import shutil
import pickle
import time
import uuid
import glob
import logging
from typing import Optional, List, Any, Dict
from pathlib import Path

from ..message import Message
from ..exceptions import (
    QueueNotFoundError, 
    QueueAlreadyExistsError, 
    MessageNotFoundError
)
from .base import StorageBackend

logger = logging.getLogger(__name__)

class FileBackend(StorageBackend):
    """
    Storage backend that persists messages to the file system.
    
    Structure:
    root_dir/
      queues/
        <queue_name>/
          pending/      # Messages waiting to be processed
          processing/   # Messages currently being processed
          dlq/          # Dead letter queue
    """
    
    def __init__(self, root_dir: str = "data"):
        self.root_dir = Path(root_dir)
        self.queues_dir = self.root_dir / "queues"
        self._lock_file = self.root_dir / "broker.lock"
        
    def initialize(self) -> None:
        """Setup directories."""
        os.makedirs(self.queues_dir, exist_ok=True)
        
    def close(self) -> None:
        """Cleanup resources."""
        pass

    def _get_queue_path(self, name: str) -> Path:
        return self.queues_dir / name

    def create_queue(self, name: str) -> None:
        """Create a new queue directory structure."""
        queue_path = self._get_queue_path(name)
        if queue_path.exists():
            raise QueueAlreadyExistsError(f"Queue '{name}' already exists")
            
        os.makedirs(queue_path / "pending")
        os.makedirs(queue_path / "processing")
        os.makedirs(queue_path / "dlq")

    def delete_queue(self, name: str) -> None:
        """Delete a queue and all its messages."""
        queue_path = self._get_queue_path(name)
        if not queue_path.exists():
            raise QueueNotFoundError(f"Queue '{name}' does not exist")
            
        shutil.rmtree(queue_path)

    def enqueue(self, queue_name: str, message: Message) -> None:
        """Add a message to the queue."""
        queue_path = self._get_queue_path(queue_name)
        if not queue_path.exists():
            raise QueueNotFoundError(f"Queue '{queue_name}' does not exist")
            
        # Create filename: <timestamp>_<uuid>.msg
        filename = f"{time.time()}_{message.id}.msg"
        file_path = queue_path / "pending" / filename
        
        # Atomic write
        temp_path = file_path.with_suffix(".tmp")
        with open(temp_path, "wb") as f:
            pickle.dump(message, f)
        
        os.replace(temp_path, file_path)

    def dequeue(self, queue_name: str, timeout: float = None) -> Optional[Message]:
        """
        Retrieve a message from the queue.
        Uses polling for timeout.
        """
        queue_path = self._get_queue_path(queue_name)
        if not queue_path.exists():
            raise QueueNotFoundError(f"Queue '{queue_name}' does not exist")
            
        pending_dir = queue_path / "pending"
        processing_dir = queue_path / "processing"
        
        start_time = time.time()
        
        while True:
            # List files, sorted by name (timestamp)
            files = sorted(list(pending_dir.glob("*.msg")))
            
            if files:
                # Try to claim the first file
                target_file = files[0]
                dest_file = processing_dir / target_file.name
                
                try:
                    # Atomic move to processing
                    os.rename(target_file, dest_file)
                    
                    # Read and return
                    with open(dest_file, "rb") as f:
                        message = pickle.load(f)
                    return message
                    
                except FileNotFoundError:
                    # File was taken by another worker, try next
                    continue
                except OSError as e:
                    logger.error(f"Error moving file {target_file}: {e}")
                    continue
            
            # Check timeout
            if timeout is None:
                return None
                
            if time.time() - start_time >= timeout:
                return None
                
            time.sleep(0.1) # Poll interval

    def ack(self, queue_name: str, message_id: str) -> None:
        """Acknowledge processing (delete file)."""
        queue_path = self._get_queue_path(queue_name)
        processing_dir = queue_path / "processing"
        
        # Find file with this message ID
        # Since filename contains ID, we can search for it
        # Pattern: *_{message_id}.msg
        files = list(processing_dir.glob(f"*_{message_id}.msg"))
        
        if not files:
            # Might have been already acked or moved
            return
            
        for file_path in files:
            try:
                os.remove(file_path)
            except OSError:
                pass

    def nack(self, queue_name: str, message_id: str, error: str = None) -> None:
        """Negative acknowledgement."""
        queue_path = self._get_queue_path(queue_name)
        if not queue_path.exists():
            raise QueueNotFoundError(f"Queue '{queue_name}' does not exist")

        processing_dir = queue_path / "processing"
        pending_dir = queue_path / "pending"
        
        files = list(processing_dir.glob(f"*_{message_id}.msg"))
        if not files:
            return
            
        file_path = files[0]
        
        # Read message to update retry count
        try:
            with open(file_path, "rb") as f:
                message = pickle.load(f)
            
            message.retry_count += 1
            if error:
                message.error = error
            
            # Write back updated message
            with open(file_path, "wb") as f:
                pickle.dump(message, f)
                
            # Move back to pending
            dest_file = pending_dir / file_path.name
            os.rename(file_path, dest_file)
            
        except (OSError, pickle.PickleError) as e:
            logger.error(f"Error nacking message {message_id}: {e}")

    # --- DLQ Operations ---

    def get_dlq_messages(self, queue_name: str) -> List[Message]:
        """List messages in the DLQ."""
        queue_path = self._get_queue_path(queue_name)
        if not queue_path.exists():
            raise QueueNotFoundError(f"Queue '{queue_name}' does not exist")
            
        dlq_dir = queue_path / "dlq"
        messages = []
        
        for file_path in sorted(dlq_dir.glob("*.msg")):
            try:
                with open(file_path, "rb") as f:
                    messages.append(pickle.load(f))
            except (OSError, pickle.PickleError):
                continue
                
        return messages

    def requeue_from_dlq(self, queue_name: str, message_id: str) -> None:
        """Move message from DLQ back to main queue."""
        queue_path = self._get_queue_path(queue_name)
        if not queue_path.exists():
            raise QueueNotFoundError(f"Queue '{queue_name}' does not exist")
            
        dlq_dir = queue_path / "dlq"
        pending_dir = queue_path / "pending"
        
        files = list(dlq_dir.glob(f"*_{message_id}.msg"))
        if not files:
            raise MessageNotFoundError(f"Message {message_id} not found in DLQ")
            
        file_path = files[0]
        dest_file = pending_dir / file_path.name
        
        os.rename(file_path, dest_file)

    def delete_dlq_message(self, queue_name: str, message_id: str) -> None:
        """Permanently delete a message from DLQ."""
        queue_path = self._get_queue_path(queue_name)
        if not queue_path.exists():
            raise QueueNotFoundError(f"Queue '{queue_name}' does not exist")
            
        dlq_dir = queue_path / "dlq"
        files = list(dlq_dir.glob(f"*_{message_id}.msg"))
        
        if not files:
            raise MessageNotFoundError(f"Message {message_id} not found in DLQ")
            
        os.remove(files[0])
        
    def move_to_dlq(self, queue_name: str, message: Message) -> None:
        """Move a message to the DLQ."""
        queue_path = self._get_queue_path(queue_name)
        if not queue_path.exists():
            raise QueueNotFoundError(f"Queue '{queue_name}' does not exist")
            
        # It could be in processing (if coming from worker) or pending
        # We assume the caller (broker) handles the logic, but here we need to find the file
        # Usually move_to_dlq is called after a failed processing attempt, so it should be in processing
        
        processing_dir = queue_path / "processing"
        dlq_dir = queue_path / "dlq"
        
        files = list(processing_dir.glob(f"*_{message.id}.msg"))
        
        if not files:
            # Fallback check pending if not in processing
            pending_dir = queue_path / "pending"
            files = list(pending_dir.glob(f"*_{message.id}.msg"))
            
        if not files:
            # If we can't find the file, we should create it in DLQ (maybe it was in memory before?)
            # But for FileBackend, it should be on disk.
            # Let's just write it to DLQ directly if not found
            filename = f"{time.time()}_{message.id}.msg"
            file_path = dlq_dir / filename
            with open(file_path, "wb") as f:
                pickle.dump(message, f)
            return

        file_path = files[0]
        dest_file = dlq_dir / file_path.name
        
        # Update content before moving (e.g. error message)
        with open(file_path, "wb") as f:
            pickle.dump(message, f)
            
        os.rename(file_path, dest_file)

    # --- Metrics Support ---
    
    def get_queue_depth(self, queue_name: str) -> int:
        """Get current number of pending messages."""
        queue_path = self._get_queue_path(queue_name)
        if not queue_path.exists():
            raise QueueNotFoundError(f"Queue '{queue_name}' does not exist")
            
        return len(list((queue_path / "pending").glob("*.msg")))
    
    def get_dlq_depth(self, queue_name: str) -> int:
        """Get current number of messages in DLQ."""
        queue_path = self._get_queue_path(queue_name)
        if not queue_path.exists():
            raise QueueNotFoundError(f"Queue '{queue_name}' does not exist")
            
        return len(list((queue_path / "dlq").glob("*.msg")))
