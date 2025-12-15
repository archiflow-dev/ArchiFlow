"""
Integration tests for FileBackend persistence with MessageBroker.
"""
import unittest
import sys
import os
import shutil
import tempfile
import time
import threading

# Add project root to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.message_queue.broker import MessageBroker
from src.message_queue.storage.file import FileBackend
from src.message_queue.exceptions import QueueAlreadyExistsError

class TestFilePersistenceIntegration(unittest.TestCase):
    """
    Integration tests verifying full broker flow with file persistence.
    """
    
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.queue_name = "integration_test_queue"
        
    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
            
    def test_persistence_across_restart(self):
        """
        Test flow:
        1. Start Broker A with FileBackend.
        2. Publish messages.
        3. Stop Broker A.
        4. Start Broker B with same FileBackend path.
        5. Verify messages exist.
        6. Consume messages with worker.
        """
        # === Phase 1: Produce ===
        storage_a = FileBackend(root_dir=self.test_dir)
        broker_a = MessageBroker(storage_backend=storage_a)
        broker_a.start()
        
        broker_a.create_queue(self.queue_name)
        
        messages = ["msg_1", "msg_2", "msg_3"]
        for msg in messages:
            broker_a.enqueue(self.queue_name, msg)
            
        # Verify they are in storage
        self.assertEqual(broker_a._storage.get_queue_depth(self.queue_name), 3)
        
        broker_a.stop()
        
        # === Phase 2: Restart & Consume ===
        storage_b = FileBackend(root_dir=self.test_dir)
        broker_b = MessageBroker(storage_backend=storage_b)
        broker_b.start()
        
        # Re-attach to queue
        # Note: create_queue will raise QueueAlreadyExistsError because it's on disk,
        # but we need to register it in the broker's memory config.
        # In a real app, we might have a 'load_queues' method, but for now we catch the error.
        try:
            broker_b.create_queue(self.queue_name)
        except QueueAlreadyExistsError:
            pass
            
        # Verify messages persisted (checking storage directly as metrics might reset)
        # Note: broker.get_queue_depth delegates to storage, so it should return correct count from disk
        self.assertEqual(broker_b._storage.get_queue_depth(self.queue_name), 3)
        
        # Consume
        received = []
        event = threading.Event()
        
        def worker(payload):
            received.append(payload)
            if len(received) == 3:
                event.set()
                
        broker_b.register_worker(self.queue_name, worker)
        
        # Wait for processing
        event.wait(timeout=5.0)
        
        self.assertEqual(len(received), 3)
        self.assertEqual(set(received), set(messages))
        
        # Verify queue is empty
        self.assertEqual(broker_b._storage.get_queue_depth(self.queue_name), 0)
        
        broker_b.stop()

    def test_dlq_persistence(self):
        """
        Test that DLQ messages persist across restarts.
        """
        # === Phase 1: Fail & DLQ ===
        storage_a = FileBackend(root_dir=self.test_dir)
        broker_a = MessageBroker(storage_backend=storage_a)
        broker_a.start()
        
        broker_a.create_queue(self.queue_name, max_retries=0) # Fail immediately
        
        # Worker that always fails
        broker_a.register_worker(self.queue_name, lambda x: 1/0)
        
        broker_a.enqueue(self.queue_name, "fail_msg")
        
        # Wait for processing and move to DLQ
        time.sleep(1.0)
        
        dlq_msgs = broker_a.get_dlq_messages(self.queue_name)
        self.assertEqual(len(dlq_msgs), 1)
        
        broker_a.stop()
        
        # === Phase 2: Restart & Verify DLQ ===
        storage_b = FileBackend(root_dir=self.test_dir)
        broker_b = MessageBroker(storage_backend=storage_b)
        broker_b.start()
        
        try:
            broker_b.create_queue(self.queue_name, max_retries=0)
        except QueueAlreadyExistsError:
            pass
            
        dlq_msgs_b = broker_b.get_dlq_messages(self.queue_name)
        self.assertEqual(len(dlq_msgs_b), 1)
        self.assertEqual(dlq_msgs_b[0].payload, "fail_msg")
        
        broker_b.stop()

if __name__ == '__main__':
    unittest.main()
