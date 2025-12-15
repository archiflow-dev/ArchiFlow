"""
Unit tests for Phase 2: Metrics Collection and Management.

Tests cover:
- MetricsCollector initialization
- Queue metrics tracking (published, processed, failed, dlq_count, processing time)
- Topic metrics tracking (published, subscriber count, failed deliveries)
- System-wide metrics (total messages, uptime, active threads)
- Thread-safe metric updates
- Metric aggregation and retrieval
"""
import unittest
import time
import threading
import sys
import os

# Add project root to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.message_queue.metrics import MetricsCollector


class TestMetricsCollector(unittest.TestCase):
    """Test suite for MetricsCollector"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.metrics = MetricsCollector()
    
    # === Initialization Tests ===
    
    def test_metrics_collector_initialization(self):
        """Test MetricsCollector initializes with zero values"""
        self.assertEqual(self.metrics.get_total_messages(), 0)
        self.assertEqual(self.metrics.get_active_threads(), 0)
    
    def test_metrics_start_time_recorded(self):
        """Test that start time is recorded on initialization"""
        start_time = self.metrics.get_start_time()
        self.assertIsInstance(start_time, float)
        self.assertLessEqual(start_time, time.time())
    
    # === Queue Metrics Tests ===
    
    def test_increment_queue_published(self):
        """Test incrementing published counter for a queue"""
        self.metrics.increment_queue_published('test_queue')
        stats = self.metrics.get_queue_stats('test_queue')
        self.assertEqual(stats['published'], 1)
    
    def test_increment_queue_processed(self):
        """Test incrementing processed counter for a queue"""
        self.metrics.increment_queue_processed('test_queue')
        stats = self.metrics.get_queue_stats('test_queue')
        self.assertEqual(stats['processed'], 1)
    
    def test_increment_queue_failed(self):
        """Test incrementing failed counter for a queue"""
        self.metrics.increment_queue_failed('test_queue')
        stats = self.metrics.get_queue_stats('test_queue')
        self.assertEqual(stats['failed'], 1)
    
    def test_increment_queue_dlq_count(self):
        """Test incrementing DLQ counter for a queue"""
        self.metrics.increment_queue_dlq_count('test_queue')
        stats = self.metrics.get_queue_stats('test_queue')
        self.assertEqual(stats['dlq_count'], 1)
    
    def test_record_processing_time(self):
        """Test recording processing time for a queue"""
        self.metrics.record_processing_time('test_queue', 100.5)
        stats = self.metrics.get_queue_stats('test_queue')
        self.assertEqual(stats['avg_processing_time_ms'], 100.5)
    
    def test_multiple_processing_times_averaged(self):
        """Test that multiple processing times are averaged correctly"""
        self.metrics.record_processing_time('test_queue', 100)
        self.metrics.record_processing_time('test_queue', 200)
        self.metrics.record_processing_time('test_queue', 300)
        stats = self.metrics.get_queue_stats('test_queue')
        self.assertEqual(stats['avg_processing_time_ms'], 200)
    
    def test_set_queue_depth(self):
        """Test setting current queue depth"""
        self.metrics.set_queue_depth('test_queue', 42)
        stats = self.metrics.get_queue_stats('test_queue')
        self.assertEqual(stats['depth'], 42)
    
    def test_set_worker_count(self):
        """Test setting worker count for a queue"""
        self.metrics.set_worker_count('test_queue', 5)
        stats = self.metrics.get_queue_stats('test_queue')
        self.assertEqual(stats['worker_count'], 5)
    
    # === Topic Metrics Tests ===
    
    def test_increment_topic_published(self):
        """Test incrementing published counter for a topic"""
        self.metrics.increment_topic_published('user.created')
        stats = self.metrics.get_topic_stats('user.created')
        self.assertEqual(stats['published'], 1)
    
    def test_increment_topic_failed_delivery(self):
        """Test incrementing failed delivery counter for a topic"""
        self.metrics.increment_topic_failed_delivery('user.created')
        stats = self.metrics.get_topic_stats('user.created')
        self.assertEqual(stats['failed_deliveries'], 1)
    
    def test_set_subscriber_count(self):
        """Test setting subscriber count for a topic"""
        self.metrics.set_subscriber_count('user.created', 3)
        stats = self.metrics.get_topic_stats('user.created')
        self.assertEqual(stats['subscriber_count'], 3)
    
    # === System-Wide Metrics Tests ===
    
    def test_get_total_messages(self):
        """Test getting total messages across all queues and topics"""
        self.metrics.increment_queue_published('queue1')
        self.metrics.increment_queue_published('queue2')
        self.metrics.increment_topic_published('topic1')
        self.assertEqual(self.metrics.get_total_messages(), 3)
    
    def test_get_uptime_seconds(self):
        """Test getting system uptime in seconds"""
        time.sleep(0.1)
        uptime = self.metrics.get_uptime_seconds()
        self.assertGreaterEqual(uptime, 0.1)
        self.assertLess(uptime, 1.0)
    
    def test_get_active_thread_count(self):
        """Test getting active thread count"""
        self.metrics.set_active_threads(10)
        self.assertEqual(self.metrics.get_active_threads(), 10)
    
    def test_get_system_metrics(self):
        """Test getting complete system metrics snapshot"""
        metrics = self.metrics.get_system_metrics()
        self.assertIn('total_messages', metrics)
        self.assertIn('uptime_seconds', metrics)
        self.assertIn('active_threads', metrics)
        self.assertIn('start_time', metrics)
    
    # === Multiple Queues/Topics Tests ===
    
    def test_multiple_queues_isolated_metrics(self):
        """Test that metrics for different queues are isolated"""
        self.metrics.increment_queue_published('queue_a')
        self.metrics.increment_queue_published('queue_b')
        self.metrics.increment_queue_published('queue_b')
        
        stats_a = self.metrics.get_queue_stats('queue_a')
        stats_b = self.metrics.get_queue_stats('queue_b')
        self.assertEqual(stats_a['published'], 1)
        self.assertEqual(stats_b['published'], 2)
    
    def test_list_all_queues_with_metrics(self):
        """Test listing all queues that have metrics"""
        self.metrics.increment_queue_published('queue1')
        self.metrics.increment_queue_published('queue2')
        queues = self.metrics.list_queues()
        self.assertIn('queue1', queues)
        self.assertIn('queue2', queues)
        self.assertEqual(len(queues), 2)
    
    def test_list_all_topics_with_metrics(self):
        """Test listing all topics that have metrics"""
        self.metrics.increment_topic_published('topic1')
        self.metrics.increment_topic_published('topic2')
        topics = self.metrics.list_topics()
        self.assertIn('topic1', topics)
        self.assertIn('topic2', topics)
        self.assertEqual(len(topics), 2)
    
    # === Thread Safety Tests ===
    
    def test_concurrent_queue_increments_thread_safe(self):
        """Test that concurrent metric increments are thread-safe"""
        num_threads = 10
        increments_per_thread = 100
        
        def increment_worker():
            for _ in range(increments_per_thread):
                self.metrics.increment_queue_published('concurrent_queue')
        
        threads = [threading.Thread(target=increment_worker) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        stats = self.metrics.get_queue_stats('concurrent_queue')
        expected = num_threads * increments_per_thread
        self.assertEqual(stats['published'], expected)
    
    # === Edge Cases ===
    
    def test_get_stats_for_nonexistent_queue(self):
        """Test getting stats for a queue that doesn't exist"""
        stats = self.metrics.get_queue_stats('nonexistent_queue')
        self.assertEqual(stats['published'], 0)
        self.assertEqual(stats['processed'], 0)
    
    def test_zero_processing_time(self):
        """Test recording zero processing time"""
        self.metrics.record_processing_time('test_queue', 0)
        stats = self.metrics.get_queue_stats('test_queue')
        self.assertEqual(stats['avg_processing_time_ms'], 0)
    
    def test_get_queue_stats_returns_complete_dict(self):
        """Test that get_queue_stats returns all expected fields"""
        self.metrics.increment_queue_published('test_queue')
        stats = self.metrics.get_queue_stats('test_queue')
        expected_fields = [
            'published', 'processed', 'failed', 'dlq_count',
            'depth', 'avg_processing_time_ms', 'worker_count'
        ]
        for field in expected_fields:
            self.assertIn(field, stats)
    
    def test_get_topic_stats_returns_complete_dict(self):
        """Test that get_topic_stats returns all expected fields"""
        self.metrics.increment_topic_published('test_topic')
        stats = self.metrics.get_topic_stats('test_topic')
        expected_fields = ['published', 'subscriber_count', 'failed_deliveries']
        for field in expected_fields:
            self.assertIn(field, stats)
    
    def test_metrics_snapshot_immutability(self):
        """Test that returned stats dicts don't affect internal state"""
        stats = self.metrics.get_queue_stats('test_queue')
        stats['published'] = 9999  # Modify returned dict
        
        # Get stats again, should be unaffected
        new_stats = self.metrics.get_queue_stats('test_queue')
        self.assertNotEqual(new_stats['published'], 9999)
    
    def test_decrement_dlq_count(self):
        """Test decrementing DLQ count"""
        self.metrics.increment_queue_dlq_count('test_queue')
        self.metrics.increment_queue_dlq_count('test_queue')
        stats = self.metrics.get_queue_stats('test_queue')
        self.assertEqual(stats['dlq_count'], 2)
        
        self.metrics.decrement_queue_dlq_count('test_queue')
        stats = self.metrics.get_queue_stats('test_queue')
        self.assertEqual(stats['dlq_count'], 1)
    
    def test_reset_queue_metrics(self):
        """Test resetting metrics for a specific queue"""
        self.metrics.increment_queue_published('test_queue')
        self.metrics.increment_queue_processed('test_queue')
        
        self.metrics.reset_queue_metrics('test_queue')
        
        stats = self.metrics.get_queue_stats('test_queue')
        self.assertEqual(stats['published'], 0)
        self.assertEqual(stats['processed'], 0)


if __name__ == '__main__':
    unittest.main()
