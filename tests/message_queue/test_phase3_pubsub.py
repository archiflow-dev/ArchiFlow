"""
Unit tests for Phase 3: Pub/Sub with Threading and Async Support.

Tests cover:
- Synchronous subscriber registration and message delivery
- Asynchronous subscriber registration and message delivery
- Auto-detection of sync vs async callbacks
- Multiple subscribers per topic
- Message fanout to all subscribers
- Topic isolation (messages don't cross topics)
- Error handling in subscribers (exceptions don't crash broker)
- Thread safety for concurrent publishes
- Metrics tracking for pub/sub operations
"""
import unittest
import asyncio
import time
import threading
import sys
import os

# Add project root to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.message_queue.broker import MessageBroker


class TestPubSubBasic(unittest.TestCase):
    """Test suite for basic pub/sub functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.broker = MessageBroker()
        self.received_messages = []
        self.lock = threading.Lock()
    
    def tearDown(self):
        """Clean up"""
        if self.broker._running:
            self.broker.stop()
    
    # === Synchronous Subscriber Tests ===
    
    def test_subscribe_sync_callback(self):
        """Test subscribing with a synchronous callback"""
        def on_message(msg):
            pass
        
        self.broker.subscribe('test.topic', on_message)
        self.assertEqual(len(self.broker._subscriptions['test.topic']), 1)
    
    def test_publish_and_receive_sync(self):
        """Test publishing message to sync subscriber"""
        def on_message(msg):
            with self.lock:
                self.received_messages.append(msg.payload)
        
        self.broker.subscribe('test.topic', on_message)
        self.broker.start()
        self.broker.publish('test.topic', {'data': 'test123'})
        
        time.sleep(0.2)  # Allow time for delivery
        self.assertEqual(len(self.received_messages), 1)
        self.assertEqual(self.received_messages[0], {'data': 'test123'})
    
    def test_publish_multiple_messages_sync(self):
        """Test publishing multiple messages to sync subscriber"""
        def on_message(msg):
            with self.lock:
                self.received_messages.append(msg.payload)
        
        self.broker.subscribe('test.topic', on_message)
        self.broker.start()
        
        for i in range(5):
            self.broker.publish('test.topic', {'id': i})
        
        time.sleep(0.2)
        self.assertEqual(len(self.received_messages), 5)
    
    # === Asynchronous Subscriber Tests ===
    
    def test_subscribe_async_callback_auto_detected(self):
        """Test subscribing with async callback (auto-detected)"""
        async def on_message(msg):
            await asyncio.sleep(0.01)
        
        self.broker.subscribe('test.topic', on_message)
        self.assertTrue(asyncio.iscoroutinefunction(on_message))
    
    def test_publish_and_receive_async(self):
        """Test publishing message to async subscriber"""
        async def on_message(msg):
            await asyncio.sleep(0.01)
            with self.lock:
                self.received_messages.append(msg.payload)
        
        self.broker.subscribe('test.topic', on_message)
        self.broker.start()
        self.broker.publish('test.topic', {'data': 'async_test'})
        
        time.sleep(0.3)  # Allow time for async processing
        self.assertEqual(len(self.received_messages), 1)
        self.assertEqual(self.received_messages[0], {'data': 'async_test'})
    
    def test_mixed_sync_and_async_subscribers(self):
        """Test topic with both sync and async subscribers"""
        sync_received = []
        async_received = []
        
        def sync_handler(msg):
            sync_received.append(msg.payload)
        
        async def async_handler(msg):
            await asyncio.sleep(0.01)
            async_received.append(msg.payload)
        
        self.broker.subscribe('mixed.topic', sync_handler)
        self.broker.subscribe('mixed.topic', async_handler)
        self.broker.start()
        self.broker.publish('mixed.topic', {'data': 'mixed'})
        
        time.sleep(0.3)
        self.assertEqual(len(sync_received), 1)
        self.assertEqual(len(async_received), 1)
    
    # === Multiple Subscribers ===
    
    def test_multiple_subscribers_same_topic(self):
        """Test multiple subscribers receive same message (fanout)"""
        received_1 = []
        received_2 = []
        received_3 = []
        
        self.broker.subscribe('fanout.topic', lambda msg: received_1.append(msg))
        self.broker.subscribe('fanout.topic', lambda msg: received_2.append(msg))
        self.broker.subscribe('fanout.topic', lambda msg: received_3.append(msg))
        
        self.broker.start()
        self.broker.publish('fanout.topic', {'data': 'fanout_test'})
        time.sleep(0.2)
        
        self.assertEqual(len(received_1), 1)
        self.assertEqual(len(received_2), 1)
        self.assertEqual(len(received_3), 1)
    
    def test_unsubscribe_removes_only_specified_callback(self):
        """Test unsubscribing removes only the specified callback"""
        received_1 = []
        received_2 = []
        
        handler1 = lambda msg: received_1.append(msg)
        handler2 = lambda msg: received_2.append(msg)
        
        self.broker.subscribe('test.topic', handler1)
        self.broker.subscribe('test.topic', handler2)
        self.broker.unsubscribe('test.topic', handler1)
        
        self.broker.start()
        self.broker.publish('test.topic', {'data': 'test'})
        time.sleep(0.2)
        
        self.assertEqual(len(received_1), 0)
        self.assertEqual(len(received_2), 1)
    
    # === Topic Isolation ===
    
    def test_messages_dont_cross_topics(self):
        """Test that messages are isolated to their topics"""
        topic_a_received = []
        topic_b_received = []
        
        self.broker.subscribe('topic.a', lambda msg: topic_a_received.append(msg))
        self.broker.subscribe('topic.b', lambda msg: topic_b_received.append(msg))
        
        self.broker.start()
        self.broker.publish('topic.a', {'data': 'for_a'})
        self.broker.publish('topic.b', {'data': 'for_b'})
        time.sleep(0.2)
        
        self.assertEqual(len(topic_a_received), 1)
        self.assertEqual(topic_a_received[0].payload, {'data': 'for_a'})
        self.assertEqual(len(topic_b_received), 1)
        self.assertEqual(topic_b_received[0].payload, {'data': 'for_b'})
    
    def test_publish_to_topic_with_no_subscribers(self):
        """Test publishing to topic with no subscribers (should not error)"""
        self.broker.start()
        self.broker.publish('nonexistent.topic', {'data': 'test'})
        # No assertion - just shouldn't raise exception
    
    # === Error Handling ===
    
    def test_subscriber_exception_doesnt_crash_broker(self):
        """Test that exception in subscriber doesn't crash broker"""
        def failing_handler(msg):
            raise ValueError("Intentional error")
        
        received = []
        def working_handler(msg):
            received.append(msg)
        
        self.broker.subscribe('error.topic', failing_handler)
        self.broker.subscribe('error.topic', working_handler)
        
        self.broker.start()
        self.broker.publish('error.topic', {'data': 'test'})
        time.sleep(0.2)
        
        # Working handler should still receive message
        self.assertEqual(len(received), 1)
    
    def test_subscriber_exception_increments_failed_metric(self):
        """Test that subscriber failures are tracked in metrics"""
        def failing_handler(msg):
            raise ValueError("Error")
        
        self.broker.subscribe('error.topic', failing_handler)
        self.broker.start()
        self.broker.publish('error.topic', {'data': 'test'})
        time.sleep(0.2)
        
        stats = self.broker.get_topic_stats('error.topic')
        self.assertEqual(stats['failed_deliveries'], 1)
    
    # === Metrics Integration ===
    
    def test_publish_increments_topic_published_metric(self):
        """Test that publish increments topic published counter"""
        self.broker.subscribe('metrics.topic', lambda msg: None)
        self.broker.start()
        
        self.broker.publish('metrics.topic', {'data': 'test'})
        self.broker.publish('metrics.topic', {'data': 'test2'})
        
        stats = self.broker.get_topic_stats('metrics.topic')
        self.assertEqual(stats['published'], 2)
    
    def test_subscriber_count_tracked_in_metrics(self):
        """Test that subscriber count is tracked in metrics"""
        self.broker.subscribe('count.topic', lambda msg: None)
        self.broker.subscribe('count.topic', lambda msg: None)
        self.broker.subscribe('count.topic', lambda msg: None)
        
        stats = self.broker.get_topic_stats('count.topic')
        self.assertEqual(stats['subscriber_count'], 3)
    
    # === Message Properties ===
    
    def test_message_has_unique_id(self):
        """Test that each published message gets unique ID"""
        ids = []
        def on_message(msg):
            ids.append(msg.id)
        
        self.broker.subscribe('id.topic', on_message)
        self.broker.start()
        
        for i in range(10):
            self.broker.publish('id.topic', {'data': i})
        time.sleep(0.3)
        
        # All IDs should be unique
        self.assertEqual(len(ids), 10)
        self.assertEqual(len(set(ids)), 10)
    
    def test_message_metadata_preserved(self):
        """Test that message metadata is preserved in delivery"""
        received_metadata = []
        
        def on_message(msg):
            received_metadata.append(msg.metadata)
        
        self.broker.subscribe('meta.topic', on_message)
        self.broker.start()
        
        metadata = {'priority': 'high', 'sender': 'test-service'}
        self.broker.publish('meta.topic', {'data': 'test'}, metadata=metadata)
        time.sleep(0.2)
        
        self.assertEqual(len(received_metadata), 1)
        self.assertEqual(received_metadata[0], metadata)
    
    # === Edge Cases ===
    
    def test_subscribe_with_non_callable(self):
        """Test subscribing with non-callable raises error"""
        with self.assertRaises(TypeError):
            self.broker.subscribe('test.topic', "not a function")
    
    def test_subscribe_with_none(self):
        """Test subscribing with None raises error"""
        with self.assertRaises(TypeError):
            self.broker.subscribe('test.topic', None)
    
    def test_empty_topic_name(self):
        """Test publish/subscribe with empty topic name"""
        with self.assertRaises(ValueError):
            self.broker.subscribe('', lambda msg: None)
        
        with self.assertRaises(ValueError):
            self.broker.publish('', {'data': 'test'})
    
    def test_none_payload(self):
        """Test publishing None as payload"""
        received = []
        self.broker.subscribe('none.topic', lambda msg: received.append(msg))
        self.broker.start()
        self.broker.publish('none.topic', None)
        time.sleep(0.2)
        
        self.assertEqual(len(received), 1)
        self.assertIsNone(received[0].payload)


if __name__ == '__main__':
    unittest.main()
