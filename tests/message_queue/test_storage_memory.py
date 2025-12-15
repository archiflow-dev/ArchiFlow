"""
Unit tests for Storage Backends (Phase 1).
"""
import unittest
import sys
import os
import time
from concurrent.futures import ThreadPoolExecutor

# Add project root to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.message_queue.storage.memory import InMemoryBackend
from src.message_queue.message import Message
from src.message_queue.exceptions import QueueNotFoundError, QueueAlreadyExistsError, MessageNotFoundError

class TestInMemoryBackend(unittest.TestCase):
    
    def setUp(self):
        self.storage = InMemoryBackend()
        self.storage.initialize()
        
    def tearDown(self):
        self.storage.close()
        
    def test_create_delete_queue(self):
        self.storage.create_queue('test_queue')
        self.storage.enqueue('test_queue', Message.create('test', 'payload'))
        self.storage.delete_queue('test_queue')
        
        with self.assertRaises(QueueNotFoundError):
            self.storage.enqueue('test_queue', Message.create('test', 'payload'))
            
    def test_enqueue_dequeue_ack(self):
        self.storage.create_queue('q1')
        msg = Message.create('q1', 'data')
        self.storage.enqueue('q1', msg)
        
        dequeued = self.storage.dequeue('q1', timeout=0.1)
        self.assertEqual(dequeued.id, msg.id)
        
        # Should be in processing
        self.assertIn(msg.id, self.storage._processing['q1'])
        
        self.storage.ack('q1', msg.id)
        
        # Should be gone
        self.assertNotIn(msg.id, self.storage._processing['q1'])
        self.assertIsNone(self.storage.dequeue('q1', timeout=0.1))
        
    def test_nack_requeues(self):
        self.storage.create_queue('q1')
        msg = Message.create('q1', 'data')
        self.storage.enqueue('q1', msg)
        
        dequeued = self.storage.dequeue('q1')
        self.storage.nack('q1', dequeued.id)
        
        # Should be back in queue
        dequeued_again = self.storage.dequeue('q1')
        self.assertEqual(dequeued_again.id, msg.id)
        
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
            
        with ThreadPoolExecutor(max_workers=2) as executor:
            p = executor.submit(producer)
            c = executor.submit(consumer)
            
            p.result()
            consumed_count = c.result()
            
        self.assertEqual(consumed_count, count)
        self.assertEqual(self.storage.get_queue_depth('concurrent_q'), 0)

if __name__ == '__main__':
    unittest.main()
