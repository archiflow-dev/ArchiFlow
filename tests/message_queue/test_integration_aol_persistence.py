"""
Integration tests for AOLBackend persistence with MessageBroker.
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
from src.message_queue.storage.aol import AOLBackend
from src.message_queue.exceptions import QueueAlreadyExistsError

class TestAOLPersistenceIntegration(unittest.TestCase):
    """
    Integration tests verifying full broker flow with AOL persistence.
    """
    
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.queue_name = "integration_test_queue_aol"
        
    def tearDown(self):
        # Wait a bit for threads to cleanup
        time.sleep(0.2)
        if os.path.exists(self.test_dir):
            for i in range(5):
                try:
                    shutil.rmtree(self.test_dir)
                    break
                except PermissionError:
                    time.sleep(0.2)
            else:
                # Final attempt or ignore
                try:
                    shutil.rmtree(self.test_dir)
                except PermissionError:
                    print(f"Warning: Could not clean up {self.test_dir}")
            
    def test_persistence_across_restart(self):
        """
        Test flow:
        1. Start Broker A with AOLBackend.
        2. Publish messages.
        3. Stop Broker A.
        4. Start Broker B with same AOLBackend path.
        5. Verify messages exist.
        6. Consume messages with worker.
        """
        # === Phase 1: Produce ===
        storage_a = AOLBackend(root_dir=self.test_dir)
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
        storage_b = AOLBackend(root_dir=self.test_dir)
        broker_b = MessageBroker(storage_backend=storage_b)
        broker_b.start()
        
        # Re-attach to queue
        try:
            broker_b.create_queue(self.queue_name)
        except QueueAlreadyExistsError:
            pass
            
        # Verify messages persisted
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
        
        # Verify queue is empty (in terms of pending messages)
        self.assertEqual(broker_b._storage.get_queue_depth(self.queue_name), 0)
        
        broker_b.stop()

    def test_dlq_persistence(self):
        """
        Test that DLQ messages persist across restarts in AOL.
        """
        # === Phase 1: Fail & DLQ ===
        storage_a = AOLBackend(root_dir=self.test_dir)
        broker_a = MessageBroker(storage_backend=storage_a)
        broker_a.start()
        
        broker_a.create_queue(self.queue_name, max_retries=0) # Fail immediately
        
        # Worker that always fails
        broker_a.register_worker(self.queue_name, lambda x: 1/0)
        
        broker_a.enqueue(self.queue_name, "fail_msg")
        
        # Wait for processing and move to DLQ
        time.sleep(1.0)
        
        # Check DLQ depth via storage directly
        self.assertEqual(broker_a._storage.get_dlq_depth(self.queue_name), 1)
        
        broker_a.stop()
        
        # === Phase 2: Restart & Verify DLQ ===
        storage_b = AOLBackend(root_dir=self.test_dir)
        broker_b = MessageBroker(storage_backend=storage_b)
        broker_b.start()
        
        try:
            broker_b.create_queue(self.queue_name, max_retries=0)
        except QueueAlreadyExistsError:
            pass
            
        # Verify DLQ depth persisted
        self.assertEqual(broker_b._storage.get_dlq_depth(self.queue_name), 1)
        
        # Verify content
        dlq_msgs = broker_b.get_dlq_messages(self.queue_name)
        self.assertEqual(len(dlq_msgs), 1)
        self.assertEqual(dlq_msgs[0].payload, "fail_msg")
        
        broker_b.stop()

if __name__ == '__main__':
    unittest.main()
