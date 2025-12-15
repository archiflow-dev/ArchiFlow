"""
AOLBackend - Append-Only Log storage backend.
"""
import os
import struct
import pickle
import time
import zlib
import threading
import logging
import shutil
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
from dataclasses import dataclass

from ..message import Message
from ..exceptions import (
    QueueNotFoundError, 
    QueueAlreadyExistsError, 
    MessageNotFoundError
)
from .base import StorageBackend

logger = logging.getLogger(__name__)

# --- Constants ---
MAGIC_BYTE = 0xA1
HEADER_FORMAT = ">B I I B d"  # Magic(1), CRC(4), Length(4), Type(1), Timestamp(8)
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

TYPE_ENQUEUE = 0
TYPE_ACK = 1
TYPE_NACK = 2
TYPE_PROCESSING = 3
TYPE_DLQ = 4

@dataclass
class IndexEntry:
    offset: int
    length: int
    state: str  # 'PENDING', 'PROCESSING', 'DLQ', 'DELETED'
    retry_count: int
    timestamp: float

class LogRecord:
    """Handles serialization and deserialization of log records."""
    
    @staticmethod
    def serialize(record_type: int, payload: bytes) -> bytes:
        """
        Create a binary record.
        Format: [Magic][CRC][Length][Type][Timestamp][Payload]
        """
        timestamp = time.time()
        length = len(payload)
        crc = zlib.crc32(payload)
        
        header = struct.pack(HEADER_FORMAT, MAGIC_BYTE, crc, length, record_type, timestamp)
        return header + payload

    @staticmethod
    def read_header(file_handle) -> Optional[Tuple[int, int, int, float]]:
        """
        Read and unpack header.
        Returns: (crc, length, type, timestamp) or None if EOF.
        """
        header_bytes = file_handle.read(HEADER_SIZE)
        if len(header_bytes) < HEADER_SIZE:
            return None
            
        magic, crc, length, record_type, timestamp = struct.unpack(HEADER_FORMAT, header_bytes)
        
        if magic != MAGIC_BYTE:
            raise ValueError(f"Invalid magic byte: {hex(magic)}")
            
        return crc, length, record_type, timestamp

class AOLBackend(StorageBackend):
    """
    Storage backend using an Append-Only Log.
    """
    
    def __init__(self, root_dir: str = "data_aol"):
        self.root_dir = Path(root_dir)
        self.queues_dir = self.root_dir / "queues"
        
        # In-memory index: queue_name -> {msg_id -> IndexEntry}
        self._indices: Dict[str, Dict[str, IndexEntry]] = {}
        
        # File handles: queue_name -> file object
        self._files: Dict[str, Any] = {}
        
        # Locks: queue_name -> RLock
        self._locks: Dict[str, threading.RLock] = {}
        
        self._global_lock = threading.RLock() # Protects queue creation/deletion

    def initialize(self) -> None:
        """Setup directories and rebuild indices."""
        os.makedirs(self.queues_dir, exist_ok=True)
        
        # Discover existing queues
        for queue_dir in self.queues_dir.iterdir():
            if queue_dir.is_dir():
                self._load_queue(queue_dir.name)

    def close(self) -> None:
        """Close all file handles."""
        with self._global_lock:
            for f in self._files.values():
                f.close()
            self._files.clear()

    def _load_queue(self, queue_name: str) -> None:
        """Initialize a single queue: open log and rebuild index."""
        queue_path = self.queues_dir / queue_name
        log_path = queue_path / "0000.log"
        
        if not log_path.exists():
            # Should not happen for valid queue dir, but handle it
            with open(log_path, "wb") as f:
                pass
        
        # Open in append binary mode for writing, read binary for reading
        # We'll keep one handle for appending (and reading if needed, but seeking might be tricky with 'ab+')
        # 'rb+' allows reading and writing, but we need to be careful with seeking to end for writes.
        f = open(log_path, "rb+")
        self._files[queue_name] = f
        self._locks[queue_name] = threading.RLock()
        self._indices[queue_name] = {}
        
        self._rebuild_index(queue_name)

    def _rebuild_index(self, queue_name: str) -> None:
        """Replay log to build in-memory index."""
        f = self._files[queue_name]
        index = self._indices[queue_name]
        
        f.seek(0)
        
        while True:
            offset = f.tell()
            try:
                header = LogRecord.read_header(f)
                if header is None:
                    break
                    
                crc, length, record_type, timestamp = header
                
                # Read payload
                payload = f.read(length)
                if len(payload) != length:
                    logger.warning(f"Truncated record in queue {queue_name} at offset {offset}")
                    break
                    
                # Verify CRC
                if zlib.crc32(payload) != crc:
                    logger.warning(f"Corrupted record in queue {queue_name} at offset {offset}")
                    continue
                
                # Process Record
                if record_type == TYPE_ENQUEUE:
                    try:
                        message = pickle.loads(payload)
                        index[message.id] = IndexEntry(
                            offset=offset,
                            length=HEADER_SIZE + length,
                            state='PENDING',
                            retry_count=message.retry_count,
                            timestamp=timestamp
                        )
                    except Exception as e:
                        logger.error(f"Failed to deserialize message at {offset}: {e}")
                        
                elif record_type == TYPE_ACK:
                    msg_id = payload.decode('utf-8')
                    if msg_id in index:
                        index[msg_id].state = 'DELETED'
                        
                elif record_type == TYPE_NACK:
                    msg_id = payload.decode('utf-8')
                    if msg_id in index:
                        index[msg_id].retry_count += 1
                        index[msg_id].state = 'PENDING'
                        
                elif record_type == TYPE_PROCESSING:
                    msg_id = payload.decode('utf-8')
                    if msg_id in index:
                        index[msg_id].state = 'PROCESSING'
                        
                elif record_type == TYPE_DLQ:
                    msg_id = payload.decode('utf-8')
                    if msg_id in index:
                        index[msg_id].state = 'DLQ'
                        
            except ValueError as e:
                logger.error(f"Error reading log for {queue_name}: {e}")
                break
                
        # Seek to end for future writes
        f.seek(0, 2)

    def create_queue(self, name: str) -> None:
        """Create a new queue."""
        with self._global_lock:
            if name in self._indices:
                raise QueueAlreadyExistsError(f"Queue '{name}' already exists")
            
            queue_path = self.queues_dir / name
            if queue_path.exists():
                 # It exists on disk but not loaded? Should have been loaded in initialize.
                 # If we are creating it, it implies we want a fresh one or it wasn't there.
                 raise QueueAlreadyExistsError(f"Queue '{name}' already exists on disk")
            
            os.makedirs(queue_path)
            log_path = queue_path / "0000.log"
            
            # Create empty file
            with open(log_path, "wb") as f:
                pass
                
            self._load_queue(name)

    def delete_queue(self, name: str) -> None:
        """Delete a queue."""
        with self._global_lock:
            if name not in self._indices:
                raise QueueNotFoundError(f"Queue '{name}' does not exist")
            
            # Close file
            with self._locks[name]:
                self._files[name].close()
                del self._files[name]
                del self._indices[name]
                del self._locks[name]
            
            # Delete directory
            shutil.rmtree(self.queues_dir / name)

    def enqueue(self, queue_name: str, message: Message) -> None:
        """Append enqueue record."""
        if queue_name not in self._indices:
            raise QueueNotFoundError(f"Queue '{queue_name}' does not exist")
            
        payload = pickle.dumps(message)
        record = LogRecord.serialize(TYPE_ENQUEUE, payload)
        
        with self._locks[queue_name]:
            f = self._files[queue_name]
            f.seek(0, 2) # Seek to end
            offset = f.tell()
            f.write(record)
            f.flush()
            
            # Update index
            self._indices[queue_name][message.id] = IndexEntry(
                offset=offset,
                length=len(record),
                state='PENDING',
                retry_count=message.retry_count,
                timestamp=time.time()
            )

    def dequeue(self, queue_name: str, timeout: float = None) -> Optional[Message]:
        """Find pending message, read it, mark processing."""
        if queue_name not in self._indices:
            raise QueueNotFoundError(f"Queue '{queue_name}' does not exist")
            
        start_time = time.time()
        
        while True:
            with self._locks[queue_name]:
                index = self._indices[queue_name]
                
                # Find first PENDING message
                # Optimization: Could maintain a separate list of pending IDs to avoid scanning dict
                candidate_id = None
                candidate_entry = None
                
                # Simple scan (O(N) of total messages in index) - ok for Phase 1
                # Sort by offset (insertion order)
                sorted_entries = sorted(
                    [(mid, entry) for mid, entry in index.items() if entry.state == 'PENDING'],
                    key=lambda x: x[1].offset
                )
                
                if sorted_entries:
                    candidate_id, candidate_entry = sorted_entries[0]
                    
                    # Read message
                    f = self._files[queue_name]
                    f.seek(candidate_entry.offset)
                    
                    # Skip header to get to payload
                    # We know the length from index, but we need to verify/read properly
                    # LogRecord.read_header reads header and returns info.
                    # But we want to read the payload at (offset + HEADER_SIZE)
                    
                    f.seek(candidate_entry.offset + HEADER_SIZE)
                    payload_len = candidate_entry.length - HEADER_SIZE
                    payload = f.read(payload_len)
                    
                    message = pickle.loads(payload)
                    
                    # Mark PROCESSING in Log
                    # We append a small record saying "MsgID is now Processing"
                    # This helps crash recovery know it was being processed.
                    # For strict exactly-once or at-least-once, this is important.
                    
                    proc_payload = candidate_id.encode('utf-8')
                    proc_record = LogRecord.serialize(TYPE_PROCESSING, proc_payload)
                    f.seek(0, 2)
                    f.write(proc_record)
                    f.flush()
                    
                    # Update Index
                    candidate_entry.state = 'PROCESSING'
                    
                    return message
            
            # Timeout check
            if timeout is None:
                return None
            if time.time() - start_time >= timeout:
                return None
            
            time.sleep(0.1)

    def ack(self, queue_name: str, message_id: str) -> None:
        """Append Ack record."""
        if queue_name not in self._indices:
            raise QueueNotFoundError(f"Queue '{queue_name}' does not exist")
            
        with self._locks[queue_name]:
            index = self._indices[queue_name]
            if message_id not in index:
                # Already deleted or never existed
                return
            
            # If already in DLQ, do not delete!
            if index[message_id].state == 'DLQ':
                return
                
            payload = message_id.encode('utf-8')
            record = LogRecord.serialize(TYPE_ACK, payload)
            
            f = self._files[queue_name]
            f.seek(0, 2)
            f.write(record)
            f.flush()
            
            # Update Index
            index[message_id].state = 'DELETED'

    def nack(self, queue_name: str, message_id: str, error: str = None) -> None:
        """Append Nack record."""
        if queue_name not in self._indices:
            raise QueueNotFoundError(f"Queue '{queue_name}' does not exist")
            
        with self._locks[queue_name]:
            index = self._indices[queue_name]
            if message_id not in index:
                return
                
            payload = message_id.encode('utf-8')
            record = LogRecord.serialize(TYPE_NACK, payload)
            
            f = self._files[queue_name]
            f.seek(0, 2)
            f.write(record)
            f.flush()
            
            # Update Index
            entry = index[message_id]
            entry.retry_count += 1
            entry.state = 'PENDING' 

    # --- DLQ Operations ---

    def get_dlq_messages(self, queue_name: str) -> List[Message]:
        """List messages in DLQ state."""
        if queue_name not in self._indices:
            raise QueueNotFoundError(f"Queue '{queue_name}' does not exist")
            
        messages = []
        with self._locks[queue_name]:
            index = self._indices[queue_name]
            dlq_entries = [
                (mid, entry) for mid, entry in index.items() 
                if entry.state == 'DLQ'
            ]
            
            f = self._files[queue_name]
            for mid, entry in dlq_entries:
                f.seek(entry.offset + HEADER_SIZE)
                payload_len = entry.length - HEADER_SIZE
                payload = f.read(payload_len)
                try:
                    msg = pickle.loads(payload)
                    messages.append(msg)
                except:
                    pass
        return messages

    def move_to_dlq(self, queue_name: str, message: Message) -> None:
        """
        Mark message as DLQ. 
        """
        if queue_name not in self._indices:
            raise QueueNotFoundError(f"Queue '{queue_name}' does not exist")
            
        with self._locks[queue_name]:
            if message.id not in self._indices[queue_name]:
                return
                
            payload = message.id.encode('utf-8')
            record = LogRecord.serialize(TYPE_DLQ, payload)
            
            f = self._files[queue_name]
            f.seek(0, 2)
            f.write(record)
            f.flush()
            
            self._indices[queue_name][message.id].state = 'DLQ'

    def requeue_from_dlq(self, queue_name: str, message_id: str) -> None:
        """Move from DLQ to PENDING."""
        if queue_name not in self._indices:
            raise QueueNotFoundError(f"Queue '{queue_name}' does not exist")
            
        with self._locks[queue_name]:
            index = self._indices[queue_name]
            if message_id in index and index[message_id].state == 'DLQ':
                # We should probably write a record here too to persist the requeue
                # For now, let's just use NACK which sets to PENDING
                self.nack(queue_name, message_id)

    def delete_dlq_message(self, queue_name: str, message_id: str) -> None:
        # Force delete even if in DLQ
        if queue_name not in self._indices:
            raise QueueNotFoundError(f"Queue '{queue_name}' does not exist")
            
        with self._locks[queue_name]:
            index = self._indices[queue_name]
            if message_id not in index:
                return
            
            # Manually write ACK and update state, bypassing the check in self.ack()
            payload = message_id.encode('utf-8')
            record = LogRecord.serialize(TYPE_ACK, payload)
            
            f = self._files[queue_name]
            f.seek(0, 2)
            f.write(record)
            f.flush()
            
            index[message_id].state = 'DELETED'

    # --- Metrics ---
    
    def get_queue_depth(self, queue_name: str) -> int:
        if queue_name not in self._indices:
            raise QueueNotFoundError(f"Queue '{queue_name}' does not exist")
        
        with self._locks[queue_name]:
            return sum(1 for entry in self._indices[queue_name].values() if entry.state == 'PENDING')

    def get_dlq_depth(self, queue_name: str) -> int:
        if queue_name not in self._indices:
            raise QueueNotFoundError(f"Queue '{queue_name}' does not exist")
            
        with self._locks[queue_name]:
            return sum(1 for entry in self._indices[queue_name].values() if entry.state == 'DLQ')
            
    # --- Compaction ---
    
    def compact(self, queue_name: str) -> None:
        """
        Rewrite log to remove DELETED messages.
        Stop-the-world implementation.
        """
        if queue_name not in self._indices:
            raise QueueNotFoundError(f"Queue '{queue_name}' does not exist")
            
        with self._locks[queue_name]:
            index = self._indices[queue_name]
            f_old = self._files[queue_name]
            
            queue_path = self.queues_dir / queue_name
            temp_log_path = queue_path / "compacted.log"
            
            with open(temp_log_path, "wb") as f_new:
                # Iterate over index, write only active messages
                # We need to write them as ENQUEUE records to preserve them.
                # We also need to preserve retry counts? 
                # For Phase 1, we just re-enqueue the original message data.
                
                # Sort by offset to maintain order
                active_entries = sorted(
                    [(mid, entry) for mid, entry in index.items() if entry.state != 'DELETED'],
                    key=lambda x: x[1].offset
                )
                
                new_index = {}
                current_offset = 0
                
                for mid, entry in active_entries:
                    # Read original payload
                    f_old.seek(entry.offset + HEADER_SIZE)
                    payload_len = entry.length - HEADER_SIZE
                    payload = f_old.read(payload_len)
                    
                    # We need to reconstruct the message to potentially update retry count if we want to persist that?
                    # The payload in the log is the serialized message AT THE TIME OF ENQUEUE.
                    # It doesn't have the updated retry count from NACKs (which are separate records).
                    # If we just copy the original payload, we lose the retry count state unless we deserialize, update, reserialize.
                    
                    try:
                        msg = pickle.loads(payload)
                        msg.retry_count = entry.retry_count
                        new_payload = pickle.dumps(msg)
                        
                        # Write as ENQUEUE
                        record = LogRecord.serialize(TYPE_ENQUEUE, new_payload)
                        f_new.write(record)
                        
                        # Update new index
                        new_index[mid] = IndexEntry(
                            offset=current_offset,
                            length=len(record),
                            state=entry.state, # Preserve PENDING/DLQ/PROCESSING
                            retry_count=entry.retry_count,
                            timestamp=time.time()
                        )
                        current_offset += len(record)
                        
                    except Exception as e:
                        logger.error(f"Error compacting message {mid}: {e}")
            
            # Close old file
            f_old.close()
            
            # Swap files
            log_path = queue_path / "0000.log"
            os.replace(temp_log_path, log_path)
            
            # Re-open
            self._files[queue_name] = open(log_path, "rb+")
            self._indices[queue_name] = new_index
