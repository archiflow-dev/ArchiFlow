"""
Unit tests for Phase 6: Admin API.

Tests cover:
- Listing all queues and topics
- Getting queue statistics
- Getting topic statistics
- Getting system-wide metrics
- Purging queues
- DLQ management operations
- Edge cases for admin operations
"""
import unittest
import time
import sys
import os

# Add project root to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.message_queue.broker import MessageBroker
from src.message_queue.exceptions import QueueNotFoundError


class TestAdminAPIQueues(unittest.TestCase):
    """Test suite for queue management via Admin API"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.broker = MessageBroker()
    
    def tearDown(self):
        """Clean up"""
        if self.broker._running:
            self.broker.stop()
    
    # === List Queues ===
    
    def test_list_queues_empty(self):
        """Test listing queues when none exist"""
        queues = self.broker.list_queues()
        self.assertEqual(len(queues), 0)
    
    def test_list_queues_returns_all_queues(self):
        """Test that list_queues returns all created queues"""
        self.broker.create_queue('queue1')
        self.broker.create_queue('queue2')
        self.broker.create_queue('queue3')
        
        queues = self.broker.list_queues()
        self.assertEqual(len(queues), 3)
        self.assertIn('queue1', queues)
        self.assertIn('queue2', queues)
        self.assertIn('queue3', queues)
    
    # === List Topics ===
    
    def test_list_topics_empty(self):
        """Test listing topics when none exist"""
        topics = self.broker.list_topics()
        self.assertEqual(len(topics), 0)
    
    def test_list_topics_returns_all_topics(self):
        """Test that list_topics returns all topics with subscribers"""
        self.broker.subscribe('topic1', lambda msg: None)
        self.broker.subscribe('topic2', lambda msg: None)
        self.broker.subscribe('topic3', lambda msg: None)
        
        topics = self.broker.list_topics()
        self.assertGreaterEqual(len(topics), 3)
        self.assertIn('topic1', topics)
        self.assertIn('topic2', topics)
        self.assertIn('topic3', topics)
    
    # === Get Queue Stats ===
    
    def test_get_queue_stats_complete(self):
        """Test that get_queue_stats returns all expected fields"""
        self.broker.create_queue('stats_queue')
        stats = self.broker.get_queue_stats('stats_queue')
        
        expected_fields = [
            'published', 'processed', 'failed', 'dlq_count',
            'depth', 'avg_processing_time_ms', 'worker_count'
        ]
        for field in expected_fields:
            self.assertIn(field, stats)
    
    def test_get_queue_stats_accurate_values(self):
        """Test that queue stats show accurate values"""
        self.broker.create_queue('active_queue')
        self.broker.enqueue('active_queue', {'task': '1'})
        self.broker.enqueue('active_queue', {'task': '2'})
        
        stats = self.broker.get_queue_stats('active_queue')
        self.assertEqual(stats['published'], 2)
        self.assertEqual(stats['depth'], 2)
    
    def test_get_queue_stats_nonexistent_queue(self):
        """Test getting stats for non-existent queue"""
        # Should return defaults (all zeros)
        stats = self.broker.get_queue_stats('nonexistent')
        self.assertEqual(stats['published'], 0)
    
    # === Get Topic Stats ===
    
    def test_get_topic_stats_complete(self):
        """Test that get_topic_stats returns all expected fields"""
        self.broker.subscribe('stats_topic', lambda msg: None)
        stats = self.broker.get_topic_stats('stats_topic')
        
        expected_fields = ['published', 'subscriber_count', 'failed_deliveries']
        for field in expected_fields:
            self.assertIn(field, stats)
    
    def test_get_topic_stats_accurate_values(self):
        """Test that topic stats show accurate values"""
        self.broker.subscribe('active_topic', lambda msg: None)
        self.broker.subscribe('active_topic', lambda msg: None)
        self.broker.start()
        self.broker.publish('active_topic', {'data': 'test'})
        time.sleep(0.1)
        
        stats = self.broker.get_topic_stats('active_topic')
        self.assertEqual(stats['subscriber_count'], 2)
        self.assertEqual(stats['published'], 1)
    
    # === Get System Metrics ===
    
    def test_get_system_metrics_complete(self):
        """Test that get_system_metrics returns all expected fields"""
        metrics = self.broker.get_metrics()
        
        expected_fields = ['total_messages', 'uptime_seconds', 'active_threads', 'start_time']
        for field in expected_fields:
            self.assertIn(field, metrics)
    
    def test_get_system_metrics_uptime_increases(self):
        """Test that uptime increases over time"""
        metrics1 = self.broker.get_metrics()
        time.sleep(0.2)
        metrics2 = self.broker.get_metrics()
        
        self.assertGreater(metrics2['uptime_seconds'], metrics1['uptime_seconds'])
    
    def test_get_system_metrics_total_messages_accurate(self):
        """Test that total messages count is accurate"""
        self.broker.create_queue('queue1')
        self.broker.subscribe('topic1', lambda msg: None)
        
        self.broker.enqueue('queue1', {'task': 'test'})
        self.broker.start()
        self.broker.publish('topic1', {'data': 'test'})
        time.sleep(0.1)
        
        metrics = self.broker.get_metrics()
        self.assertEqual(metrics['total_messages'], 2)
    
    # === Purge Queue ===
    
    def test_purge_queue_removes_all_messages(self):
        """Test that purge_queue removes all messages from queue"""
        self.broker.create_queue('purge_queue')
        for i in range(10):
            self.broker.enqueue('purge_queue', {'id': i})
        
        self.assertEqual(self.broker._queues['purge_queue'].qsize(), 10)
        count = self.broker.purge_queue('purge_queue')
        
        self.assertEqual(count, 10)
        self.assertEqual(self.broker._queues['purge_queue'].qsize(), 0)
    
    def test_purge_queue_updates_depth_metric(self):
        """Test that purge updates queue depth metric"""
        self.broker.create_queue('depth_queue')
        self.broker.enqueue('depth_queue', {'task': 'test'})
        self.broker.purge_queue('depth_queue')
        
        stats = self.broker.get_queue_stats('depth_queue')
        self.assertEqual(stats['depth'], 0)
    
    def test_purge_empty_queue(self):
        """Test purging an already empty queue"""
        self.broker.create_queue('empty_queue')
        count = self.broker.purge_queue('empty_queue')
        self.assertEqual(count, 0)
    
    def test_purge_nonexistent_queue(self):
        """Test purging a non-existent queue raises error"""
        with self.assertRaises(QueueNotFoundError):
            self.broker.purge_queue('nonexistent')
    
    # === Get Queue Info ===
    
    def test_get_queue_info_returns_config_and_stats(self):
        """Test that get_queue_info returns queue config and stats"""
        self.broker.create_queue('info_queue', max_retries=5, dlq_enabled=False)
        info = self.broker.get_queue_info('info_queue')
        
        # Should include config
        self.assertEqual(info['config']['max_retries'], 5)
        self.assertFalse(info['config']['dlq_enabled'])
        
        # Should include stats
        self.assertIn('published', info['stats'])
        self.assertIn('processed', info['stats'])
    
    def test_get_queue_info_nonexistent_queue(self):
        """Test get_queue_info for non-existent queue raises error"""
        with self.assertRaises(QueueNotFoundError):
            self.broker.get_queue_info('nonexistent')
    
    # === Edge Cases ===
    
    def test_list_operations_with_many_queues_topics(self):
        """Test list operations with hundreds of queues/topics"""
        for i in range(100):
            self.broker.create_queue(f'queue_{i}')
            self.broker.subscribe(f'topic_{i}', lambda msg: None)
        
        queues = self.broker.list_queues()
        topics = self.broker.list_topics()
        
        self.assertEqual(len(queues), 100)
        self.assertGreaterEqual(len(topics), 100)
    
    def test_stats_immutability(self):
        """Test that returned stats dicts don't affect internal state"""
        self.broker.create_queue('immut_queue')
        stats = self.broker.get_queue_stats('immut_queue')
        stats['published'] = 9999  # Modify returned dict
        
        # Get stats again, should be unaffected
        new_stats = self.broker.get_queue_stats('immut_queue')
        self.assertNotEqual(new_stats['published'], 9999)
        self.assertEqual(new_stats['published'], 0)


if __name__ == '__main__':
    unittest.main()
