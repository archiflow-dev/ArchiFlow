"""
Unit tests for AOLBackend Storage.
"""
import unittest
import sys
import os
import shutil
import tempfile
import time
import struct
from concurrent.futures import ThreadPoolExecutor

# Add project root to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.message_queue.storage.aol import AOLBackend, LogRecord, TYPE_ENQUEUE, TYPE_ACK
from src.message_queue.message import Message
from src.message_queue.exceptions import QueueNotFoundError, QueueAlreadyExistsError

class TestAOLBackend(unittest.TestCase):
    
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.storage = AOLBackend(root_dir=self.test_dir)
        self.storage.initialize()
        
    def tearDown(self):
        self.storage.close()
        shutil.rmtree(self.test_dir)
        
    def test_log_record_serialization(self):
        payload = b"test_payload"
        record = LogRecord.serialize(TYPE_ENQUEUE, payload)
        
        # Verify header
        header_size = struct.calcsize(">B I I B d")
        self.assertTrue(len(record) > header_size)
        
        # Verify magic byte
        self.assertEqual(record[0], 0xA1)
        
    def test_create_delete_queue(self):
        self.storage.create_queue('test_queue')
        
        # Check directory and log file exist
        queue_path = os.path.join(self.test_dir, 'queues', 'test_queue')
        log_path = os.path.join(queue_path, '0000.log')
        self.assertTrue(os.path.exists(log_path))
        
        self.storage.enqueue('test_queue', Message.create('test', 'payload'))
        self.storage.delete_queue('test_queue')
        
        self.assertFalse(os.path.exists(queue_path))
        
    def test_enqueue_dequeue_ack(self):
        self.storage.create_queue('q1')
        msg = Message.create('q1', 'data')
        self.storage.enqueue('q1', msg)
        
        # Verify index updated
        self.assertEqual(self.storage.get_queue_depth('q1'), 1)
        
        dequeued = self.storage.dequeue('q1', timeout=0.1)
        self.assertEqual(dequeued.id, msg.id)
        
        # Should be processing
        # Note: get_queue_depth only counts PENDING in current impl
        self.assertEqual(self.storage.get_queue_depth('q1'), 0)
        
        self.storage.ack('q1', msg.id)
        
        # Should be gone from index (marked DELETED)
        # We can't easily check DELETED state from public API, but dequeue should return None
        self.assertIsNone(self.storage.dequeue('q1', timeout=0.1))
        
    def test_persistence_restart(self):
        """Verify messages persist and index rebuilds."""
        self.storage.create_queue('persist_q')
        msg1 = Message.create('persist_q', 'data1')
        msg2 = Message.create('persist_q', 'data2')
        
        self.storage.enqueue('persist_q', msg1)
        self.storage.enqueue('persist_q', msg2)
        self.storage.ack('persist_q', msg1.id) # Ack the first one
        
        # Close and reopen
        self.storage.close()
        
        new_storage = AOLBackend(root_dir=self.test_dir)
        new_storage.initialize()
        
        # Verify state
        # msg1 should be DELETED (so not in depth)
        # msg2 should be PENDING
        self.assertEqual(new_storage.get_queue_depth('persist_q'), 1)
        
        dequeued = new_storage.dequeue('persist_q', timeout=0.1)
        self.assertEqual(dequeued.id, msg2.id)
        
    def test_compaction(self):
        # Create storage with auto-compaction disabled for this test
        test_dir = tempfile.mkdtemp()
        storage = AOLBackend(root_dir=test_dir, auto_compact=False)
        storage.initialize()
        storage.create_queue('compact_q')

        try:
            # Enqueue 10 messages
            msgs = [Message.create('compact_q', f'data_{i}') for i in range(10)]
            for m in msgs:
                storage.enqueue('compact_q', m)

            # Verify all 10 are in index initially
            self.assertEqual(len(storage._indices['compact_q']), 10)

            # Ack first 5 (in refactored version, this marks deleted in-memory only)
            for i in range(5):
                storage.ack('compact_q', msgs[i].id)

            # Index still has 10 entries (5 DELETED, 5 PENDING)
            self.assertEqual(len(storage._indices['compact_q']), 10)

            # But queue depth should be 5 (only PENDING counted)
            self.assertEqual(storage.get_queue_depth('compact_q'), 5)

            # Compact - this should remove DELETED entries
            storage.compact('compact_q')

            # After compaction, deleted messages should be removed from index
            self.assertEqual(len(storage._indices['compact_q']), 5)

            # Verify remaining messages are still there
            self.assertEqual(storage.get_queue_depth('compact_q'), 5)

            dequeued = storage.dequeue('compact_q', timeout=0.1)
            self.assertEqual(dequeued.payload, 'data_5')
        finally:
            storage.close()
            shutil.rmtree(test_dir)

    def test_concurrency(self):
        """Verify thread safety with concurrent producers and consumers."""
        self.storage.create_queue('concurrent_q')
        count = 100

        def producer():
            for i in range(count):
                self.storage.enqueue('concurrent_q', Message.create('t', i))

        def consumer():
            consumed = 0
            while consumed < count:
                msg = self.storage.dequeue('concurrent_q', timeout=1.0)
                if msg:
                    self.storage.ack('concurrent_q', msg.id)
                    consumed += 1
            return consumed

        with ThreadPoolExecutor(max_workers=4) as executor:
            # multiple producers and consumers
            p1 = executor.submit(producer)
            p2 = executor.submit(producer)
            c1 = executor.submit(consumer)
            c2 = executor.submit(consumer)

            p1.result()
            p2.result()
            count1 = c1.result()
            count2 = c2.result()

        self.assertEqual(count1 + count2, count * 2)
        self.assertEqual(self.storage.get_queue_depth('concurrent_q'), 0)

    def test_segment_rotation(self):
        """Test automatic segment rotation when size threshold is exceeded."""
        # Create storage with small segment size (1KB)
        test_dir = tempfile.mkdtemp()
        storage = AOLBackend(root_dir=test_dir, segment_size_bytes=1024)
        storage.initialize()
        storage.create_queue('rotate_q')

        try:
            # Enqueue enough messages to trigger rotation
            # Each message is roughly 150-200 bytes
            for i in range(10):
                storage.enqueue('rotate_q', Message.create('rotate_q', 'x' * 100))

            # Check that multiple segments were created
            queue_path = os.path.join(test_dir, 'queues', 'rotate_q')
            log_files = [f for f in os.listdir(queue_path) if f.endswith('.log')]
            self.assertGreater(len(log_files), 1, "Should have created multiple segments")

            # Verify messages are still accessible across segments
            self.assertEqual(storage.get_queue_depth('rotate_q'), 10)

            # Dequeue all messages
            for i in range(10):
                msg = storage.dequeue('rotate_q', timeout=0.1)
                self.assertIsNotNone(msg)
                storage.ack('rotate_q', msg.id)

        finally:
            storage.close()
            shutil.rmtree(test_dir)

    def test_auto_compaction(self):
        """Test that auto-compaction triggers when deletion threshold is reached."""
        # Create storage with auto-compaction enabled
        test_dir = tempfile.mkdtemp()
        storage = AOLBackend(root_dir=test_dir, auto_compact=True)
        storage.initialize()
        storage.create_queue('auto_compact_q')

        try:
            # Enqueue 10 messages
            msgs = [Message.create('auto_compact_q', f'data_{i}') for i in range(10)]
            for m in msgs:
                storage.enqueue('auto_compact_q', m)

            # Initially 10 messages in index
            self.assertEqual(len(storage._indices['auto_compact_q']), 10)

            # Ack 5 messages (50% deletion ratio - should trigger auto-compaction)
            for i in range(5):
                storage.ack('auto_compact_q', msgs[i].id)

            # Auto-compaction should have run, removing deleted entries
            # (triggered by _maybe_auto_compact in ack())
            time.sleep(0.1)  # Give it a moment
            self.assertEqual(len(storage._indices['auto_compact_q']), 5)
            self.assertEqual(storage.get_queue_depth('auto_compact_q'), 5)

        finally:
            storage.close()
            shutil.rmtree(test_dir)

    def test_optimized_dequeue_performance(self):
        """Verify O(log N) dequeue using heap instead of O(N) scan."""
        self.storage.create_queue('perf_q')

        # Enqueue 100 messages
        for i in range(100):
            self.storage.enqueue('perf_q', Message.create('perf_q', i))

        # Verify pending heap is being used
        self.assertEqual(len(self.storage._pending_heaps['perf_q']), 100)

        # Dequeue should be fast (heap pop)
        start = time.time()
        for i in range(50):
            msg = self.storage.dequeue('perf_q', timeout=0.1)
            self.assertIsNotNone(msg)
            self.storage.ack('perf_q', msg.id)
        duration = time.time() - start

        # Should complete quickly (< 1 second for 50 dequeues)
        self.assertLess(duration, 1.0)

        # Verify heap size decreased
        # Note: heap may have deleted entries still in it, filtered during dequeue
        self.assertGreater(len(self.storage._pending_heaps['perf_q']), 0)

if __name__ == '__main__':
    unittest.main()
