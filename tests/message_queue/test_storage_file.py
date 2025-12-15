"""
Unit tests for FileBackend Storage.
"""
import unittest
import sys
import os
import shutil
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor

# Add project root to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.message_queue.storage.file import FileBackend
from src.message_queue.message import Message
from src.message_queue.exceptions import QueueNotFoundError, QueueAlreadyExistsError, MessageNotFoundError

class TestFileBackend(unittest.TestCase):
    
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.storage = FileBackend(root_dir=self.test_dir)
        self.storage.initialize()
        
    def tearDown(self):
        self.storage.close()
        shutil.rmtree(self.test_dir)
        
    def test_create_delete_queue(self):
        self.storage.create_queue('test_queue')
        
        # Check directory exists
        queue_path = os.path.join(self.test_dir, 'queues', 'test_queue')
        self.assertTrue(os.path.exists(queue_path))
        self.assertTrue(os.path.exists(os.path.join(queue_path, 'pending')))
        
        self.storage.enqueue('test_queue', Message.create('test', 'payload'))
        self.storage.delete_queue('test_queue')
        
        self.assertFalse(os.path.exists(queue_path))
        
        with self.assertRaises(QueueNotFoundError):
            self.storage.enqueue('test_queue', Message.create('test', 'payload'))
            
    def test_enqueue_dequeue_ack(self):
        self.storage.create_queue('q1')
        msg = Message.create('q1', 'data')
        self.storage.enqueue('q1', msg)
        
        # Verify file exists
        queue_path = os.path.join(self.test_dir, 'queues', 'q1')
        pending_files = os.listdir(os.path.join(queue_path, 'pending'))
        self.assertEqual(len(pending_files), 1)
        
        dequeued = self.storage.dequeue('q1', timeout=0.1)
        self.assertEqual(dequeued.id, msg.id)
        
        # Should be in processing, not pending
        self.assertEqual(len(os.listdir(os.path.join(queue_path, 'pending'))), 0)
        self.assertEqual(len(os.listdir(os.path.join(queue_path, 'processing'))), 1)
        
        self.storage.ack('q1', msg.id)
        
        # Should be gone
        self.assertEqual(len(os.listdir(os.path.join(queue_path, 'processing'))), 0)
        self.assertIsNone(self.storage.dequeue('q1', timeout=0.1))
        
    def test_persistence_restart(self):
        """Verify messages persist across backend restarts."""
        self.storage.create_queue('persist_q')
        msg = Message.create('persist_q', 'important_data')
        self.storage.enqueue('persist_q', msg)
        
        # Simulate restart by creating new backend instance pointing to same dir
        new_storage = FileBackend(root_dir=self.test_dir)
        new_storage.initialize()
        
        dequeued = new_storage.dequeue('persist_q', timeout=0.1)
        self.assertIsNotNone(dequeued)
        self.assertEqual(dequeued.id, msg.id)
        self.assertEqual(dequeued.payload, 'important_data')
        
    def test_nack_requeues(self):
        self.storage.create_queue('q1')
        msg = Message.create('q1', 'data')
        self.storage.enqueue('q1', msg)
        
        dequeued = self.storage.dequeue('q1')
        self.storage.nack('q1', dequeued.id)
        
        # Should be back in pending
        queue_path = os.path.join(self.test_dir, 'queues', 'q1')
        self.assertEqual(len(os.listdir(os.path.join(queue_path, 'pending'))), 1)
        self.assertEqual(len(os.listdir(os.path.join(queue_path, 'processing'))), 0)
        
        dequeued_again = self.storage.dequeue('q1')
        self.assertEqual(dequeued_again.id, msg.id)
        self.assertEqual(dequeued_again.retry_count, 1)
        
    def test_dlq_operations(self):
        self.storage.create_queue('q1')
        msg = Message.create('q1', 'bad_data')
        
        self.storage.move_to_dlq('q1', msg)
        
        dlq = self.storage.get_dlq_messages('q1')
        self.assertEqual(len(dlq), 1)
        self.assertEqual(dlq[0].id, msg.id)
        
        self.storage.requeue_from_dlq('q1', msg.id)
        dlq = self.storage.get_dlq_messages('q1')
        self.assertEqual(len(dlq), 0)
        
        dequeued = self.storage.dequeue('q1')
        self.assertEqual(dequeued.id, msg.id)
        
    def test_concurrency(self):
        self.storage.create_queue('concurrent_q')
        count = 50  # Lower count for file I/O test speed
        
        def producer():
            for i in range(count):
                self.storage.enqueue('concurrent_q', Message.create('t', i))
                
        def consumer():
            consumed = 0
            while consumed < count:
                msg = self.storage.dequeue('concurrent_q', timeout=2.0)
                if msg:
                    self.storage.ack('concurrent_q', msg.id)
                    consumed += 1
            return consumed
            
        with ThreadPoolExecutor(max_workers=2) as executor:
            p = executor.submit(producer)
            c = executor.submit(consumer)
            
            p.result()
            consumed_count = c.result()
            
        self.assertEqual(consumed_count, count)
        self.assertEqual(self.storage.get_queue_depth('concurrent_q'), 0)

if __name__ == '__main__':
    unittest.main()
