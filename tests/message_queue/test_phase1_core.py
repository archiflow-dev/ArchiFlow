"""
Unit tests for Phase 1: Core Message and Broker components.

Tests cover:
- Message dataclass creation and validation
- QueueConfig dataclass
- MessageBroker initialization
- Basic publish/subscribe without threading
"""
import unittest
import time
import sys
import os

# Add project root to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.message_queue.message import Message, QueueConfig
from src.message_queue.broker import MessageBroker
from src.message_queue.exceptions import QueueAlreadyExistsError


class TestMessage(unittest.TestCase):
    """Test suite for Message dataclass"""
    
    def test_message_creation_with_required_fields(self):
        """Test creating a message with only required fields"""
        msg = Message(
            id="msg-001",
            topic="test.topic",
            payload={"data": "test"},
            timestamp=time.time()
        )
        self.assertEqual(msg.id, "msg-001")
        self.assertEqual(msg.topic, "test.topic")
        self.assertEqual(msg.payload, {"data": "test"})
        self.assertIsInstance(msg.timestamp, float)
        self.assertEqual(msg.retry_count, 0)
        self.assertEqual(msg.max_retries, 3)
        self.assertIsNone(msg.error)
        self.assertEqual(msg.metadata, {})

    def test_message_create_factory_method(self):
        """Test Message.create() factory method"""
        msg = Message.create(topic="test.topic", payload={"data": "test"})
        
        # Should have auto-generated ID and timestamp
        self.assertIsNotNone(msg.id)
        self.assertIsInstance(msg.id, str)
        self.assertGreater(len(msg.id), 0)
        self.assertIsInstance(msg.timestamp, float)
        self.assertEqual(msg.topic, "test.topic")
        self.assertEqual(msg.payload, {"data": "test"})


class TestQueueConfig(unittest.TestCase):
    """Test suite for QueueConfig dataclass"""
    
    def test_queue_config_with_defaults(self):
        """Test creating QueueConfig with default values"""
        config = QueueConfig(name="test_queue")
        
        self.assertEqual(config.name, "test_queue")
        self.assertEqual(config.max_retries, 3)
        self.assertTrue(config.dlq_enabled)
    
    def test_queue_config_with_custom_values(self):
        """Test creating QueueConfig with custom values"""
        config = QueueConfig(
            name="custom_queue",
            max_retries=5,
            dlq_enabled=False
        )
        
        self.assertEqual(config.name, "custom_queue")
        self.assertEqual(config.max_retries, 5)
        self.assertFalse(config.dlq_enabled)


class TestMessageBrokerBasics(unittest.TestCase):
    """Test suite for basic MessageBroker functionality (no threading)"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.broker = MessageBroker()
    
    def test_broker_initialization(self):
        """Test that broker initializes with empty state"""
        self.assertIsNotNone(self.broker)
        self.assertEqual(len(self.broker._subscriptions), 0)
        self.assertEqual(len(self.broker._queue_configs), 0)
    
    def test_broker_initial_state(self):
        """Test broker's initial internal state"""
        self.assertFalse(self.broker._running)
        self.assertIsNone(self.broker._event_loop)
        self.assertEqual(len(self.broker._subscription_threads), 0)
    
    def test_subscribe_adds_callback(self):
        """Test that subscribe() adds callback to subscriptions"""
        def handler(msg):
            pass
        
        self.broker.subscribe('test.topic', handler)
        self.assertIn('test.topic', self.broker._subscriptions)
        self.assertIn(handler, self.broker._subscriptions['test.topic'])
    
    def test_subscribe_multiple_callbacks_same_topic(self):
        """Test multiple callbacks can subscribe to same topic"""
        def handler1(msg):
            pass
        
        def handler2(msg):
            pass
        
        self.broker.subscribe('test.topic', handler1)
        self.broker.subscribe('test.topic', handler2)
        
        self.assertEqual(len(self.broker._subscriptions['test.topic']), 2)
        self.assertIn(handler1, self.broker._subscriptions['test.topic'])
        self.assertIn(handler2, self.broker._subscriptions['test.topic'])
    
    def test_unsubscribe_removes_callback(self):
        """Test that unsubscribe() removes callback"""
        def handler(msg):
            pass
        
        self.broker.subscribe('test.topic', handler)
        self.assertIn(handler, self.broker._subscriptions['test.topic'])
        
        self.broker.unsubscribe('test.topic', handler)
        self.assertNotIn('test.topic', self.broker._subscriptions)
    
    def test_unsubscribe_nonexistent_callback(self):
        """Test unsubscribing a callback that doesn't exist"""
        def handler(msg):
            pass
        
        # Should not raise error
        self.broker.unsubscribe('nonexistent', handler)
    
    def test_publish_to_nonexistent_topic(self):
        """Test publishing to a topic with no subscribers"""
        # Should not raise error
        msg = self.broker.publish('nonexistent.topic', {'data': 'test'})
        self.assertIsInstance(msg, Message)
        self.assertEqual(msg.topic, 'nonexistent.topic')
    
    def test_create_queue_basic(self):
        """Test creating a queue"""
        self.broker.create_queue('test_queue')
        self.assertIn('test_queue', self.broker._queue_configs)
    
    def test_create_queue_duplicate_raises_error(self):
        """Test creating duplicate queue raises error"""
        self.broker.create_queue('test_queue')
        with self.assertRaises(QueueAlreadyExistsError):
            self.broker.create_queue('test_queue')
    
    def test_start_sets_running_flag(self):
        """Test that start() sets running flag"""
        self.assertFalse(self.broker._running)
        self.broker.start()
        self.assertTrue(self.broker._running)
    
    def test_stop_clears_running_flag(self):
        """Test that stop() clears running flag"""
        self.broker.start()
        self.assertTrue(self.broker._running)
        self.broker.stop()
        self.assertFalse(self.broker._running)


class TestMessageBrokerEdgeCases(unittest.TestCase):
    """Test suite for MessageBroker edge cases"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.broker = MessageBroker()
    
    def test_empty_topic_name(self):
        """Test behavior with empty topic name"""
        with self.assertRaises(ValueError):
            self.broker.subscribe('', lambda msg: None)
        
        with self.assertRaises(ValueError):
            self.broker.publish('', {'data': 'test'})
    
    def test_subscribe_with_none_callback(self):
        """Test subscribing with None callback (should raise error)"""
        with self.assertRaises(TypeError):
            self.broker.subscribe('test.topic', None)
    
    def test_subscribe_with_non_callable(self):
        """Test subscribing with non-callable object (should raise error)"""
        with self.assertRaises(TypeError):
            self.broker.subscribe('test.topic', "not a function")
    
    def test_empty_queue_name(self):
        """Test creating queue with empty name"""
        with self.assertRaises(ValueError):
            self.broker.create_queue('')


if __name__ == '__main__':
    unittest.main()
