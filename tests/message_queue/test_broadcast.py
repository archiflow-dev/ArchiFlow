import unittest
import sys
import os
import time
from unittest.mock import MagicMock

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

from message_queue.broker import MessageBroker
from message_queue.storage.memory import InMemoryBackend

class TestBroadcast(unittest.TestCase):
    def setUp(self):
        self.broker = MessageBroker(storage_backend=InMemoryBackend())
        self.broker.start()

    def tearDown(self):
        self.broker.stop()

    def test_broadcast_to_multiple_topics(self):
        """Test broadcasting to multiple valid topics."""
        topic1 = "topic1"
        topic2 = "topic2"
        
        # Subscribe to topics
        msgs1 = []
        msgs2 = []
        
        self.broker.subscribe(topic1, lambda m: msgs1.append(m))
        self.broker.subscribe(topic2, lambda m: msgs2.append(m))
        
        # Broadcast
        payload = {"data": "test"}
        results = self.broker.broadcast([topic1, topic2], payload)
        
        # Verify return values
        self.assertIn(topic1, results)
        self.assertIn(topic2, results)
        self.assertEqual(results[topic1].payload, payload)
        self.assertEqual(results[topic2].payload, payload)
        
        # Wait for delivery
        time.sleep(0.1)
        
        # Verify delivery
        self.assertEqual(len(msgs1), 1)
        self.assertEqual(len(msgs2), 1)
        self.assertEqual(msgs1[0].payload, payload)
        self.assertEqual(msgs2[0].payload, payload)

    def test_broadcast_empty_list(self):
        """Test broadcasting with empty list raises ValueError."""
        with self.assertRaises(ValueError):
            self.broker.broadcast([], "payload")

    def test_broadcast_partial_subscribers(self):
        """Test broadcasting where some topics have no subscribers."""
        topic1 = "topic1" # Has subscriber
        topic2 = "topic2" # No subscriber
        
        msgs1 = []
        self.broker.subscribe(topic1, lambda m: msgs1.append(m))
        
        results = self.broker.broadcast([topic1, topic2], "payload")
        
        self.assertIn(topic1, results)
        self.assertIn(topic2, results)
        
        time.sleep(0.1)
        self.assertEqual(len(msgs1), 1)

if __name__ == '__main__':
    unittest.main()
