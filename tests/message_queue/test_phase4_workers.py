"""
Unit tests for Phase 4: Worker/Task Queue System with Sync and Async Support.

Tests cover:
- Queue creation and configuration
- Task enqueueing
- Sync worker registration and processing
- Async worker registration and processing  
- Auto-detection of sync vs async workers
- Multiple workers per queue (load balancing)
- Failed task retry logic
- Worker thread lifecycle
- Metrics tracking for task processing
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
from src.message_queue.exceptions import QueueAlreadyExistsError, QueueNotFoundError


class TestWorkerQueueBasic(unittest.TestCase):
    """Test suite for basic queue and worker functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.broker = MessageBroker()
        self.processed_tasks = []
        self.lock = threading.Lock()
    
    def tearDown(self):
        """Clean up"""
        if self.broker._running:
            self.broker.stop()
    
    # === Queue Creation ===
    
    def test_create_queue_with_defaults(self):
        """Test creating queue with default settings"""
        self.broker.create_queue('test_queue')
        self.assertIn('test_queue', self.broker._queue_configs)
        config = self.broker._queue_configs['test_queue']
        self.assertEqual(config.max_retries, 3)
        self.assertTrue(config.dlq_enabled)
    
    def test_create_queue_with_custom_config(self):
        """Test creating queue with custom configuration"""
        self.broker.create_queue('custom_queue', max_retries=5, dlq_enabled=False)
        config = self.broker._queue_configs['custom_queue']
        self.assertEqual(config.max_retries, 5)
        self.assertFalse(config.dlq_enabled)
    
    def test_create_queue_creates_dlq(self):
        """Test that creating queue also creates DLQ"""
        self.broker.create_queue('test_queue', dlq_enabled=True)
        self.assertIn('test_queue', self.broker._dlqs)
    
    def test_create_duplicate_queue_raises_error(self):
        """Test creating queue with duplicate name raises error"""
        self.broker.create_queue('dup_queue')
        with self.assertRaises(QueueAlreadyExistsError):
            self.broker.create_queue('dup_queue')
    
    # === Task Enqueueing ===
    
    def test_enqueue_task_basic(self):
        """Test enqueueing a basic task"""
        self.broker.create_queue('work_queue')
        self.broker.enqueue('work_queue', {'job': 'process_data'})
        self.assertEqual(self.broker._queues['work_queue'].qsize(), 1)
    
    def test_enqueue_multiple_tasks(self):
        """Test enqueueing multiple tasks"""
        self.broker.create_queue('work_queue')
        for i in range(10):
            self.broker.enqueue('work_queue', {'job_id': i})
        self.assertEqual(self.broker._queues['work_queue'].qsize(), 10)
    
    def test_enqueue_to_nonexistent_queue_raises_error(self):
        """Test enqueuing to non-existent queue raises error"""
        with self.assertRaises(QueueNotFoundError):
            self.broker.enqueue('nonexistent', {'task': 'data'})
    
    def test_enqueue_increments_published_metric(self):
        """Test that enqueue increments published metric"""
        self.broker.create_queue('metrics_queue')
        self.broker.enqueue('metrics_queue', {'task': 'test'})
        stats = self.broker.get_queue_stats('metrics_queue')
        self.assertEqual(stats['published'], 1)
    
    # === Synchronous Workers ===
    
    def test_register_sync_worker(self):
        """Test registering a synchronous worker"""
        self.broker.create_queue('sync_queue')
        
        def worker(task):
            self.processed_tasks.append(task)
        
        self.broker.register_worker('sync_queue', worker, num_threads=1)
        self.assertIn('sync_queue', self.broker._worker_callbacks)
    
    def test_sync_worker_processes_task(self):
        """Test that sync worker processes enqueued task"""
        self.broker.create_queue('work_queue')
        processed = []
        
        def worker(task):
            processed.append(task)
        
        self.broker.register_worker('work_queue', worker)
        self.broker.start()
        self.broker.enqueue('work_queue', {'job': 'test_job'})
        
        time.sleep(0.3)
        self.assertEqual(len(processed), 1)
        self.assertEqual(processed[0], {'job': 'test_job'})
    
    def test_sync_worker_processes_multiple_tasks(self):
        """Test that sync worker processes all tasks"""
        self.broker.create_queue('work_queue')
        processed = []
        
        def worker(task):
            processed.append(task)
        
        self.broker.register_worker('work_queue', worker)
        self.broker.start()
        
        for i in range(5):
            self.broker.enqueue('work_queue', {'id': i})
        
        time.sleep(0.5)
        self.assertEqual(len(processed), 5)
    
    def test_multiple_sync_workers_same_queue(self):
        """Test multiple workers processing from same queue (load balancing)"""
        self.broker.create_queue('parallel_queue')
        processed = []
        lock = threading.Lock()
        
        def worker(task):
            time.sleep(0.05)  # Simulate work
            with lock:
                processed.append(task)
        
        self.broker.register_worker('parallel_queue', worker, num_threads=3)
        self.broker.start()
        
        for i in range(10):
            self.broker.enqueue('parallel_queue', {'id': i})
        
        time.sleep(1.5)
        self.assertEqual(len(processed), 10)
    
    # === Asynchronous Workers ===
    
    def test_register_async_worker_auto_detected(self):
        """Test registering async worker (auto-detected)"""
        self.broker.create_queue('async_queue')
        
        async def worker(task):
            await asyncio.sleep(0.01)
        
        self.broker.register_worker('async_queue', worker)
        self.assertTrue(asyncio.iscoroutinefunction(worker))
    
    def test_async_worker_processes_task(self):
        """Test that async worker processes enqueued task"""
        self.broker.create_queue('async_queue')
        processed = []
        
        async def worker(task):
            await asyncio.sleep(0.01)
            processed.append(task)
        
        self.broker.register_worker('async_queue', worker)
        self.broker.start()
        self.broker.enqueue('async_queue', {'job': 'async_job'})
        
        time.sleep(0.5)
        self.assertEqual(len(processed), 1)
    
    # === Error Handling and Retries ===
    
    def test_worker_exception_triggers_retry(self):
        """Test that worker exception triggers task retry"""
        self.broker.create_queue('retry_queue', max_retries=3)
        attempt_count = {'count': 0}
        
        def failing_worker(task):
            attempt_count['count'] += 1
            if attempt_count['count'] < 3:
                raise ValueError("Temporary failure")
            # Third attempt succeeds
        
        self.broker.register_worker('retry_queue', failing_worker)
        self.broker.start()
        self.broker.enqueue('retry_queue', {'task': 'retry_test'})
        
        time.sleep(0.5)
        self.assertEqual(attempt_count['count'], 3)
    
    def test_task_moved_to_dlq_after_max_retries(self):
        """Test that task moves to DLQ after max retries exceeded"""
        self.broker.create_queue('dlq_test', max_retries=2)
        
        def always_failing_worker(task):
            raise ValueError("Always fails")
        
        self.broker.register_worker('dlq_test', always_failing_worker)
        self.broker.start()
        self.broker.enqueue('dlq_test', {'task': 'fail'})
        
        time.sleep(0.5)
        dlq_msgs = self.broker.get_dlq_messages('dlq_test')
        self.assertEqual(len(dlq_msgs), 1)
    
    def test_successful_task_increments_processed_metric(self):
        """Test that successful processing increments processed metric"""
        self.broker.create_queue('success_queue')
        
        def worker(task):
            pass  # Success
        
        self.broker.register_worker('success_queue', worker)
        self.broker.start()
        self.broker.enqueue('success_queue', {'task': 'test'})
        
        time.sleep(0.3)
        stats = self.broker.get_queue_stats('success_queue')
        self.assertEqual(stats['processed'], 1)
    
    def test_failed_task_increments_failed_metric(self):
        """Test that final failure increments failed metric"""
        self.broker.create_queue('fail_queue', max_retries=1)
        
        def failing_worker(task):
            raise Exception("Fail")
        
        self.broker.register_worker('fail_queue', failing_worker)
        self.broker.start()
        self.broker.enqueue('fail_queue', {'task': 'test'})
        
        time.sleep(0.5)
        stats = self.broker.get_queue_stats('fail_queue')
        self.assertEqual(stats['failed'], 1)
    
    # === Processing Time Metrics ===
    
    def test_processing_time_recorded(self):
        """Test that processing time is recorded in metrics"""
        self.broker.create_queue('time_queue')
        
        def worker(task):
            time.sleep(0.1)
        
        self.broker.register_worker('time_queue', worker)
        self.broker.start()
        self.broker.enqueue('time_queue', {'task': 'test'})
        
        time.sleep(0.5)
        stats = self.broker.get_queue_stats('time_queue')
        self.assertGreaterEqual(stats['avg_processing_time_ms'], 100)
    
    # === Edge Cases ===
    
    def test_register_worker_for_nonexistent_queue(self):
        """Test registering worker for non-existent queue raises error"""
        with self.assertRaises(QueueNotFoundError):
            self.broker.register_worker('nonexistent', lambda t: None)
    
    def test_worker_with_none_callback(self):
        """Test registering None as worker raises error"""
        self.broker.create_queue('test_queue')
        with self.assertRaises(TypeError):
            self.broker.register_worker('test_queue', None)
    
    def test_worker_with_non_callable(self):
        """Test registering non-callable as worker raises error"""
        self.broker.create_queue('test_queue')
        with self.assertRaises(TypeError):
            self.broker.register_worker('test_queue', "not a function")
    
    def test_zero_worker_threads(self):
        """Test registering worker with 0 threads"""
        self.broker.create_queue('queue')
        with self.assertRaises(ValueError):
            self.broker.register_worker('queue', lambda t: None, num_threads=0)
    
    def test_enqueue_none_task(self):
        """Test enqueueing None as task (should be allowed)"""
        self.broker.create_queue('none_queue')
        self.broker.enqueue('none_queue', None)
        self.assertEqual(self.broker._queues['none_queue'].qsize(), 1)


if __name__ == '__main__':
    unittest.main()
