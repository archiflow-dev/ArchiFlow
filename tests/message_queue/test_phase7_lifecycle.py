"""
Unit tests for Phase 7: Lifecycle and Thread Management.

Tests cover:
- Broker start/stop lifecycle
- Event loop initialization for async operations
- Thread creation and management
- Graceful shutdown
- Resource cleanup
- Thread safety during lifecycle transitions
"""
import unittest
import time
import threading
import asyncio
import sys
import os

# Add project root to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.message_queue.broker import MessageBroker


class TestBrokerLifecycle(unittest.TestCase):
    """Test suite for broker lifecycle management"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.broker = MessageBroker()
    
    def tearDown(self):
        """Clean up after tests"""
        if hasattr(self, 'broker') and self.broker._running:
            self.broker.stop()
    
    # === Initialization ===
    
    def test_broker_initializes_not_running(self):
        """Test that broker initializes in stopped state"""
        self.assertFalse(self.broker._running)
    
    def test_broker_has_no_threads_before_start(self):
        """Test that no worker/subscriber threads exist before start"""
        self.assertEqual(len(self.broker._subscription_threads), 0)
        self.assertEqual(len(self.broker._workers), 0)
    
    def test_broker_has_no_event_loop_before_start(self):
        """Test that event loop is not created before start"""
        self.assertIsNone(self.broker._event_loop)
    
    # === Start ===
    
    def test_start_sets_running_flag(self):
        """Test that start() sets running flag"""
        self.broker.start()
        self.assertTrue(self.broker._running)
    
    def test_start_creates_event_loop_if_async_registered(self):
        """Test that start creates event loop if async subscribers/workers exist"""
        async def async_handler(msg):
            pass
        
        self.broker.subscribe('test', async_handler)
        self.broker.start()
        
        self.assertIsNotNone(self.broker._event_loop)
        self.assertTrue(self.broker._event_loop.is_running())
    
    def test_start_doesnt_create_event_loop_if_only_sync(self):
        """Test that event loop not created if only sync callbacks"""
        def sync_handler(msg):
            pass
        
        self.broker.subscribe('test', sync_handler)
        self.broker.start()
        
        # Event loop should be None since no async callbacks
        self.assertIsNone(self.broker._event_loop)
    
    def test_start_creates_subscriber_threads(self):
        """Test that start() creates threads for subscribers"""
        def handler(msg):
            pass
        
        self.broker.subscribe('topic1', handler)
        self.broker.subscribe('topic2', handler)
        self.broker.start()
        
        # Should have subscriber management threads
        self.assertEqual(len(self.broker._subscription_threads), 2)
    
    def test_start_creates_worker_threads(self):
        """Test that start() creates threads for workers"""
        self.broker.create_queue('work_queue')
        self.broker.register_worker('work_queue', lambda t: None, num_threads=3)
        self.broker.start()
        
        self.assertEqual(len(self.broker._workers['work_queue']), 3)
    
    def test_start_idempotent(self):
        """Test that calling start() multiple times is safe"""
        self.broker.start()
        self.broker.start()
        self.broker.start()
        self.assertTrue(self.broker._running)
    
    def test_start_after_stop_works(self):
        """Test that broker can be restarted after stop"""
        self.broker.subscribe('test', lambda msg: None)
        
        self.broker.start()
        self.assertTrue(self.broker._running)
        self.broker.stop()
        self.assertFalse(self.broker._running)
        
        self.broker.start()
        self.assertTrue(self.broker._running)
    
    # === Stop ===
    
    def test_stop_clears_running_flag(self):
        """Test that stop() clears running flag"""
        self.broker.start()
        self.broker.stop()
        self.assertFalse(self.broker._running)
    
    def test_stop_joins_all_threads(self):
        """Test that stop() waits for all threads to complete"""
        self.broker.create_queue('stop_queue')
        self.broker.register_worker('stop_queue', lambda t: time.sleep(0.01), num_threads=2)
        self.broker.start()
        
        # Threads should be alive
        workers = self.broker._workers['stop_queue']
        for thread in workers:
            self.assertTrue(thread.is_alive())
        
        self.broker.stop()
        
        # Threads should be dead
        for thread in workers:
            self.assertFalse(thread.is_alive())
    
    def test_stop_shuts_down_event_loop(self):
        """Test that stop() properly shuts down event loop"""
        async def async_handler(msg):
            pass
        
        self.broker.subscribe('test', async_handler)
        self.broker.start()
        
        loop = self.broker._event_loop
        self.assertTrue(loop.is_running())
        
        self.broker.stop()
        self.assertFalse(loop.is_running())
        self.assertIsNone(self.broker._event_loop)
    
    def test_stop_completes_in_flight_tasks(self):
        """Test that stop() allows in-flight tasks to complete"""
        self.broker.create_queue('inflight_queue')
        completed = []
        
        def slow_worker(task):
            time.sleep(0.3)
            completed.append(task)
        
        self.broker.register_worker('inflight_queue', slow_worker)
        self.broker.start()
        self.broker.enqueue('inflight_queue', {'id': 1})
        
        time.sleep(0.1)  # Let worker start
        self.broker.stop(timeout=1.0)
        
        self.assertEqual(len(completed), 1)
    
    def test_stop_idempotent(self):
        """Test that calling stop() multiple times is safe"""
        self.broker.start()
        self.broker.stop()
        self.broker.stop()
        self.broker.stop()
        self.assertFalse(self.broker._running)
    
    def test_stop_before_start(self):
        """Test that stop() before start() is safe"""
        self.broker.stop()
        self.assertFalse(self.broker._running)
    
    # === Thread Safety During Lifecycle ===
    
    def test_subscribe_during_running(self):
        """Test subscribing while broker is running"""
        self.broker.start()
        self.broker.subscribe('dynamic', lambda msg: None)
        self.assertIn('dynamic', self.broker._subscription_threads)
    
    def test_create_queue_during_running(self):
        """Test creating queue while broker is running"""
        self.broker.start()
        self.broker.create_queue('dynamic_queue')
        self.assertIn('dynamic_queue', self.broker._queues)
    
    def test_concurrent_start_calls(self):
        """Test concurrent calls to start()"""
        def start_worker():
            self.broker.start()
        
        threads = [threading.Thread(target=start_worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        self.assertTrue(self.broker._running)
    
    # === Resource Cleanup ===
    
    def test_no_thread_leaks_after_stop(self):
        """Test that no threads are left running after stop"""
        # Get baseline thread count (excluding current test thread)
        initial_threads = threading.enumerate()
        initial_count = len(initial_threads)
        
        self.broker.create_queue('leak_test')
        self.broker.register_worker('leak_test', lambda t: None, num_threads=5)
        self.broker.subscribe('topic', lambda msg: None)
        
        self.broker.start()
        time.sleep(0.1)
        self.broker.stop()
        time.sleep(0.2)  # Allow threads to cleanup
        
        final_threads = threading.enumerate()
        final_count = len(final_threads)
        
        # We might have some daemon threads lingering depending on python version/env
        # but we should definitely not have our worker threads
        worker_threads = [t for t in final_threads if 'worker-leak_test' in t.name]
        self.assertEqual(len(worker_threads), 0)
    
    # === Edge Cases ===
    
    def test_start_with_no_subscribers_or_workers(self):
        """Test starting broker with no subscribers or workers"""
        self.broker.start()
        self.assertTrue(self.broker._running)
        self.broker.stop()


if __name__ == '__main__':
    unittest.main()
