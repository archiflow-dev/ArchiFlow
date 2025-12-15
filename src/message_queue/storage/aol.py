"""
AOLBackend - Refactored Append-Only Log storage backend.

Improvements:
1. Automatic segment rotation when files exceed size threshold
2. Optimized deletion - mark deleted in-memory, batch write in compaction
3. Optimized dequeue - O(log N) with heap instead of O(N) scan
4. Periodic auto-compaction
"""
import os
import struct
import pickle
import time
import zlib
import threading
import logging
import shutil
import heapq
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

# Segment rotation threshold (10MB default)
DEFAULT_SEGMENT_SIZE_BYTES = 10 * 1024 * 1024

# Auto-compaction threshold (when deleted % exceeds this)
AUTO_COMPACT_DELETED_RATIO = 0.5  # Compact when 50% of messages are deleted

# Auto-compaction minimum interval (seconds)
AUTO_COMPACT_MIN_INTERVAL = 300  # 5 minutes


@dataclass
class IndexEntry:
    offset: int
    length: int
    state: str  # 'PENDING', 'PROCESSING', 'DLQ', 'DELETED'
    retry_count: int
    timestamp: float
    segment_id: int = 0  # Which segment file this message is in


@dataclass
class PendingMessage:
    """Heap entry for pending messages (for O(log N) dequeue)."""
    offset: int
    timestamp: float
    segment_id: int
    message_id: str

    def __lt__(self, other):
        # Sort by timestamp (FIFO order)
        return self.timestamp < other.timestamp


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
    Storage backend using an Append-Only Log with automatic segmentation.
    """

    def __init__(
        self,
        root_dir: str = "data_aol",
        segment_size_bytes: int = DEFAULT_SEGMENT_SIZE_BYTES,
        auto_compact: bool = True
    ):
        self.root_dir = Path(root_dir)
        self.queues_dir = self.root_dir / "queues"
        self.segment_size_bytes = segment_size_bytes
        self.auto_compact_enabled = auto_compact

        # In-memory index: queue_name -> {msg_id -> IndexEntry}
        self._indices: Dict[str, Dict[str, IndexEntry]] = {}

        # Pending message heaps: queue_name -> heap of PendingMessage
        self._pending_heaps: Dict[str, List[PendingMessage]] = {}

        # Current segment IDs: queue_name -> current_segment_id
        self._current_segments: Dict[str, int] = {}

        # File handles: (queue_name, segment_id) -> file object
        self._files: Dict[Tuple[str, int], Any] = {}

        # Locks: queue_name -> RLock
        self._locks: Dict[str, threading.RLock] = {}

        # Last compaction time: queue_name -> timestamp
        self._last_compaction: Dict[str, float] = {}

        self._global_lock = threading.RLock()

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
        """Initialize a single queue: discover segments and rebuild index."""
        queue_path = self.queues_dir / queue_name

        # Find all segment files
        segment_files = sorted(queue_path.glob("*.log"))

        if not segment_files:
            # Create initial segment
            log_path = queue_path / "0000.log"
            with open(log_path, "wb") as f:
                pass
            segment_files = [log_path]

        self._locks[queue_name] = threading.RLock()
        self._indices[queue_name] = {}
        self._pending_heaps[queue_name] = []

        # Determine current segment ID from filenames
        max_segment_id = 0
        for seg_file in segment_files:
            seg_id = int(seg_file.stem)  # e.g., "0000" -> 0
            max_segment_id = max(max_segment_id, seg_id)

            # Open file for reading
            f = open(seg_file, "rb+")
            self._files[(queue_name, seg_id)] = f

            # Rebuild index from this segment
            self._rebuild_index_from_segment(queue_name, seg_id, f)

        self._current_segments[queue_name] = max_segment_id

        # Make sure current segment file is open for appending
        current_seg = (queue_name, max_segment_id)
        if current_seg in self._files:
            f = self._files[current_seg]
            f.seek(0, 2)  # Seek to end for appending

    def _rebuild_index_from_segment(self, queue_name: str, segment_id: int, f: Any) -> None:
        """Replay log from one segment file to build in-memory index."""
        index = self._indices[queue_name]
        pending_heap = self._pending_heaps[queue_name]

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
                    logger.warning(f"Truncated record in queue {queue_name} seg {segment_id} at offset {offset}")
                    break

                # Verify CRC
                if zlib.crc32(payload) != crc:
                    logger.warning(f"Corrupted record in queue {queue_name} seg {segment_id} at offset {offset}")
                    continue

                # Process Record
                if record_type == TYPE_ENQUEUE:
                    try:
                        message = pickle.loads(payload)
                        entry = IndexEntry(
                            offset=offset,
                            length=HEADER_SIZE + length,
                            state='PENDING',
                            retry_count=message.retry_count,
                            timestamp=timestamp,
                            segment_id=segment_id
                        )
                        index[message.id] = entry

                        # Add to pending heap
                        heapq.heappush(pending_heap, PendingMessage(
                            offset=offset,
                            timestamp=timestamp,
                            segment_id=segment_id,
                            message_id=message.id
                        ))
                    except Exception as e:
                        logger.error(f"Failed to deserialize message at {offset}: {e}")

                elif record_type == TYPE_ACK:
                    msg_id = payload.decode('utf-8')
                    if msg_id in index:
                        index[msg_id].state = 'DELETED'
                        # Note: message stays in heap, filtered out during dequeue

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
                logger.error(f"Error reading log for {queue_name} seg {segment_id}: {e}")
                break

    def _get_current_segment_file(self, queue_name: str) -> Any:
        """Get the file handle for the current (active) segment."""
        seg_id = self._current_segments[queue_name]
        return self._files[(queue_name, seg_id)]

    def _rotate_segment_if_needed(self, queue_name: str) -> None:
        """Check if current segment exceeds size limit and rotate if needed."""
        f = self._get_current_segment_file(queue_name)
        current_size = f.tell()

        if current_size >= self.segment_size_bytes:
            logger.info(f"Rotating segment for queue {queue_name} (size: {current_size} bytes)")

            # DON'T close current file - we still need it for reading old messages
            # Just flush it
            f.flush()

            # Create new segment
            old_seg_id = self._current_segments[queue_name]
            new_seg_id = old_seg_id + 1
            self._current_segments[queue_name] = new_seg_id

            queue_path = self.queues_dir / queue_name
            new_log_path = queue_path / f"{new_seg_id:04d}.log"

            with open(new_log_path, "wb") as nf:
                pass

            # Open for appending
            new_file = open(new_log_path, "rb+")
            new_file.seek(0, 2)
            self._files[(queue_name, new_seg_id)] = new_file

    def _maybe_auto_compact(self, queue_name: str) -> None:
        """Trigger automatic compaction if conditions are met."""
        if not self.auto_compact_enabled:
            return

        # Check if enough time has passed since last compaction
        last_compact = self._last_compaction.get(queue_name, 0)
        if time.time() - last_compact < AUTO_COMPACT_MIN_INTERVAL:
            return

        # Check deletion ratio
        index = self._indices[queue_name]
        if not index:
            return

        deleted_count = sum(1 for entry in index.values() if entry.state == 'DELETED')
        total_count = len(index)

        if deleted_count / total_count >= AUTO_COMPACT_DELETED_RATIO:
            logger.info(f"Auto-compacting queue {queue_name} ({deleted_count}/{total_count} deleted)")
            try:
                self.compact(queue_name)
                self._last_compaction[queue_name] = time.time()
            except Exception as e:
                logger.error(f"Auto-compaction failed for {queue_name}: {e}")

    def create_queue(self, name: str) -> None:
        """Create a new queue."""
        with self._global_lock:
            if name in self._indices:
                raise QueueAlreadyExistsError(f"Queue '{name}' already exists")

            queue_path = self.queues_dir / name
            if queue_path.exists():
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

            # Close all segment files for this queue
            with self._locks[name]:
                seg_id = 0
                while (name, seg_id) in self._files:
                    self._files[(name, seg_id)].close()
                    del self._files[(name, seg_id)]
                    seg_id += 1

                del self._indices[name]
                del self._pending_heaps[name]
                del self._current_segments[name]
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
            # Check for segment rotation
            self._rotate_segment_if_needed(queue_name)

            f = self._get_current_segment_file(queue_name)
            f.seek(0, 2)  # Seek to end
            offset = f.tell()
            f.write(record)
            f.flush()

            seg_id = self._current_segments[queue_name]

            # Update index
            entry = IndexEntry(
                offset=offset,
                length=len(record),
                state='PENDING',
                retry_count=message.retry_count,
                timestamp=time.time(),
                segment_id=seg_id
            )
            self._indices[queue_name][message.id] = entry

            # Add to pending heap for fast dequeue
            heapq.heappush(self._pending_heaps[queue_name], PendingMessage(
                offset=offset,
                timestamp=time.time(),
                segment_id=seg_id,
                message_id=message.id
            ))

    def dequeue(self, queue_name: str, timeout: float = None) -> Optional[Message]:
        """Find pending message using heap (O(log N)), read it, mark processing."""
        if queue_name not in self._indices:
            raise QueueNotFoundError(f"Queue '{queue_name}' does not exist")

        start_time = time.time()

        while True:
            with self._locks[queue_name]:
                index = self._indices[queue_name]
                pending_heap = self._pending_heaps[queue_name]

                # Pop from heap until we find a valid PENDING message
                while pending_heap:
                    candidate = heapq.heappop(pending_heap)

                    # Check if message still exists and is PENDING
                    if candidate.message_id not in index:
                        continue

                    entry = index[candidate.message_id]
                    if entry.state != 'PENDING':
                        continue

                    # Found valid pending message!
                    # Read message from correct segment
                    seg_file = self._files[(queue_name, entry.segment_id)]
                    seg_file.seek(entry.offset + HEADER_SIZE)
                    payload_len = entry.length - HEADER_SIZE
                    payload = seg_file.read(payload_len)

                    message = pickle.loads(payload)

                    # Mark PROCESSING in Log (write to current segment)
                    proc_payload = candidate.message_id.encode('utf-8')
                    proc_record = LogRecord.serialize(TYPE_PROCESSING, proc_payload)

                    current_file = self._get_current_segment_file(queue_name)
                    current_file.seek(0, 2)
                    current_file.write(proc_record)
                    current_file.flush()

                    # Update Index
                    entry.state = 'PROCESSING'

                    return message

            # No pending messages found
            if timeout is None:
                return None
            if time.time() - start_time >= timeout:
                return None

            time.sleep(0.1)

    def ack(self, queue_name: str, message_id: str) -> None:
        """Mark message as deleted in-memory only (optimized)."""
        if queue_name not in self._indices:
            raise QueueNotFoundError(f"Queue '{queue_name}' does not exist")

        with self._locks[queue_name]:
            index = self._indices[queue_name]
            if message_id not in index:
                return

            # If already in DLQ, do not delete!
            if index[message_id].state == 'DLQ':
                return

            # Optimized: Just mark deleted in-memory
            # No log write! Will be cleaned up during compaction
            index[message_id].state = 'DELETED'

            # Trigger auto-compaction check
            self._maybe_auto_compact(queue_name)

    def nack(self, queue_name: str, message_id: str, error: str = None) -> None:
        """Append Nack record and re-add to pending heap."""
        if queue_name not in self._indices:
            raise QueueNotFoundError(f"Queue '{queue_name}' does not exist")

        with self._locks[queue_name]:
            index = self._indices[queue_name]
            if message_id not in index:
                return

            entry = index[message_id]

            # Write NACK record
            payload = message_id.encode('utf-8')
            record = LogRecord.serialize(TYPE_NACK, payload)

            f = self._get_current_segment_file(queue_name)
            f.seek(0, 2)
            f.write(record)
            f.flush()

            # Update Index
            entry.retry_count += 1
            entry.state = 'PENDING'

            # Re-add to pending heap
            heapq.heappush(self._pending_heaps[queue_name], PendingMessage(
                offset=entry.offset,
                timestamp=entry.timestamp,
                segment_id=entry.segment_id,
                message_id=message_id
            ))

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

            for mid, entry in dlq_entries:
                seg_file = self._files[(queue_name, entry.segment_id)]
                seg_file.seek(entry.offset + HEADER_SIZE)
                payload_len = entry.length - HEADER_SIZE
                payload = seg_file.read(payload_len)
                try:
                    msg = pickle.loads(payload)
                    messages.append(msg)
                except:
                    pass
        return messages

    def move_to_dlq(self, queue_name: str, message: Message) -> None:
        """Mark message as DLQ."""
        if queue_name not in self._indices:
            raise QueueNotFoundError(f"Queue '{queue_name}' does not exist")

        with self._locks[queue_name]:
            if message.id not in self._indices[queue_name]:
                return

            payload = message.id.encode('utf-8')
            record = LogRecord.serialize(TYPE_DLQ, payload)

            f = self._get_current_segment_file(queue_name)
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
                self.nack(queue_name, message_id)

    def delete_dlq_message(self, queue_name: str, message_id: str) -> None:
        """Force delete even if in DLQ (in-memory mark)."""
        if queue_name not in self._indices:
            raise QueueNotFoundError(f"Queue '{queue_name}' does not exist")

        with self._locks[queue_name]:
            index = self._indices[queue_name]
            if message_id not in index:
                return

            # Optimized: Just mark deleted
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
        Rewrite segments to remove DELETED messages.
        Creates a single compacted segment.
        """
        if queue_name not in self._indices:
            raise QueueNotFoundError(f"Queue '{queue_name}' does not exist")

        with self._locks[queue_name]:
            index = self._indices[queue_name]

            queue_path = self.queues_dir / queue_name
            temp_log_path = queue_path / "compacted.log"

            # Close all existing segment files
            seg_id = 0
            old_files = []
            while (queue_name, seg_id) in self._files:
                f = self._files[(queue_name, seg_id)]
                old_files.append((seg_id, f))
                f.close()
                del self._files[(queue_name, seg_id)]
                seg_id += 1

            # Create compacted file
            with open(temp_log_path, "wb") as f_new:
                # Collect active messages (not DELETED)
                active_entries = sorted(
                    [(mid, entry) for mid, entry in index.items() if entry.state != 'DELETED'],
                    key=lambda x: x[1].timestamp  # Maintain time order
                )

                new_index = {}
                new_pending_heap = []
                current_offset = 0

                for mid, entry in active_entries:
                    # Re-open old segment file temporarily to read
                    old_seg_path = queue_path / f"{entry.segment_id:04d}.log"
                    with open(old_seg_path, "rb") as f_old:
                        f_old.seek(entry.offset + HEADER_SIZE)
                        payload_len = entry.length - HEADER_SIZE
                        payload = f_old.read(payload_len)

                    try:
                        msg = pickle.loads(payload)
                        msg.retry_count = entry.retry_count
                        new_payload = pickle.dumps(msg)

                        # Write as ENQUEUE
                        record = LogRecord.serialize(TYPE_ENQUEUE, new_payload)
                        f_new.write(record)

                        # Update new index
                        new_entry = IndexEntry(
                            offset=current_offset,
                            length=len(record),
                            state=entry.state,  # Preserve PENDING/DLQ/PROCESSING
                            retry_count=entry.retry_count,
                            timestamp=entry.timestamp,
                            segment_id=0  # All in segment 0 after compaction
                        )
                        new_index[mid] = new_entry

                        # Add to new pending heap if PENDING
                        if entry.state == 'PENDING':
                            heapq.heappush(new_pending_heap, PendingMessage(
                                offset=current_offset,
                                timestamp=entry.timestamp,
                                segment_id=0,
                                message_id=mid
                            ))

                        current_offset += len(record)

                    except Exception as e:
                        logger.error(f"Error compacting message {mid}: {e}")

            # Delete old segment files
            for old_seg_id, _ in old_files:
                old_path = queue_path / f"{old_seg_id:04d}.log"
                if old_path.exists():
                    os.remove(old_path)

            # Rename compacted file to 0000.log
            final_path = queue_path / "0000.log"
            os.replace(temp_log_path, final_path)

            # Re-open as current segment
            new_file = open(final_path, "rb+")
            new_file.seek(0, 2)  # Seek to end for appending
            self._files[(queue_name, 0)] = new_file

            # Update state
            self._indices[queue_name] = new_index
            self._pending_heaps[queue_name] = new_pending_heap
            self._current_segments[queue_name] = 0
