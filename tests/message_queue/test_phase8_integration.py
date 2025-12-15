"""
Integration tests for Phase 8: End-to-End System Verification.

Tests cover:
- Complete workflows combining Pub/Sub and Worker Queues
- Complex retry and DLQ scenarios
- System stress testing and load handling
- Long-running stability
- Cross-component interactions (Metrics + Admin + Core)
"""
import unittest
import time
import threading
import random
import sys
import os

# Add project root to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.message_queue.broker import MessageBroker


class TestIntegration(unittest.TestCase):
    """Test suite for system integration and stress testing"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.broker = MessageBroker()
    
    def tearDown(self):
        """Clean up after tests"""
        if hasattr(self, 'broker') and self.broker._running:
            self.broker.stop()
    
    # === End-to-End Workflows ===
    
    def test_workflow_pubsub_triggers_worker(self):
        """Test workflow where pub/sub subscriber enqueues task for worker"""
        self.broker.create_queue('processing_queue')
        processed_events = []
        
        # Worker processes the task
        def worker(task):
            processed_events.append(task)
        
        self.broker.register_worker('processing_queue', worker)
        
        # Subscriber listens to topic and enqueues task
        def subscriber(msg):
            self.broker.enqueue('processing_queue', {'source': msg.payload})
        
        self.broker.subscribe('incoming_events', subscriber)
        self.broker.start()
        
        # Publish event
        self.broker.publish('incoming_events', 'event_data')
        
        # Wait for flow to complete
        time.sleep(0.5)
        
        self.assertEqual(len(processed_events), 1)
        self.assertEqual(processed_events[0], {'source': 'event_data'})
        
        # Verify metrics for both
        topic_stats = self.broker.get_topic_stats('incoming_events')
        queue_stats = self.broker.get_queue_stats('processing_queue')
        
        self.assertEqual(topic_stats['published'], 1)
        self.assertEqual(queue_stats['processed'], 1)
    
    def test_workflow_worker_publishes_result(self):
        """Test workflow where worker publishes result to topic"""
        self.broker.create_queue('job_queue')
        results = []
        
        # Subscriber collects results
        def result_handler(msg):
            results.append(msg.payload)
        
        self.broker.subscribe('job_results', result_handler)
        
        # Worker performs job and publishes result
        def worker(task):
            result = f"processed_{task['id']}"
            self.broker.publish('job_results', result)
        
        self.broker.register_worker('job_queue', worker)
        self.broker.start()
        
        # Enqueue jobs
        self.broker.enqueue('job_queue', {'id': 1})
        self.broker.enqueue('job_queue', {'id': 2})
        
        time.sleep(0.5)
        
        self.assertEqual(len(results), 2)
        self.assertIn('processed_1', results)
        self.assertIn('processed_2', results)
    
    # === Complex Error Handling ===
    
    def test_retry_storm_handling(self):
        """Test system stability under heavy retry load"""
        self.broker.create_queue('unstable_queue', max_retries=5)
        
        # Worker fails 50% of the time
        def flaky_worker(task):
            if random.random() < 0.5:
                raise ValueError("Random failure")
        
        self.broker.register_worker('unstable_queue', flaky_worker, num_threads=5)
        self.broker.start()
        
        # Enqueue many tasks
        for i in range(50):
            self.broker.enqueue('unstable_queue', {'id': i})
        
        # Allow time for processing and retries
        time.sleep(2.0)
        
        stats = self.broker.get_queue_stats('unstable_queue')
        
        # Total processed + dlq should equal 50
        total_finished = stats['processed'] + stats['dlq_count']
        self.assertEqual(total_finished, 50)
    
    def test_dlq_recovery_workflow(self):
        """Test full DLQ recovery workflow: Fail -> DLQ -> Fix -> Requeue -> Success"""
        self.broker.create_queue('critical_queue', max_retries=1)
        
        # Phase 1: Worker fails
        fail_flag = {'should_fail': True}
        
        def worker(task):
            if fail_flag['should_fail']:
                raise ValueError("System down")
            # Success
        
        self.broker.register_worker('critical_queue', worker)
        self.broker.start()
        
        self.broker.enqueue('critical_queue', {'important': 'data'})
        
        time.sleep(0.5)
        
        # Verify in DLQ
        dlq = self.broker.get_dlq_messages('critical_queue')
        self.assertEqual(len(dlq), 1)
        
        # Phase 2: Fix system and requeue
        fail_flag['should_fail'] = False
        msg_id = dlq[0].id
        
        self.broker.requeue_from_dlq('critical_queue', msg_id)
        
        time.sleep(0.5)
        
        # Verify success
        stats = self.broker.get_queue_stats('critical_queue')
        self.assertEqual(stats['processed'], 1)
        self.assertEqual(stats['dlq_count'], 0)
    
    # === Stress Testing ===
    
    def test_high_concurrency_load(self):
        """Test high concurrency with mixed workload"""
        # Setup
        queue_count = 5
        topic_count = 5
        msgs_per_component = 50
        
        for i in range(queue_count):
            q_name = f'stress_q_{i}'
            self.broker.create_queue(q_name)
            self.broker.register_worker(q_name, lambda t: time.sleep(0.001), num_threads=2)
            
        for i in range(topic_count):
            t_name = f'stress_t_{i}'
            self.broker.subscribe(t_name, lambda m: None)
        
        self.broker.start()
        
        # Generate load
        start_time = time.time()
        
        def load_generator():
            for i in range(msgs_per_component):
                # Randomly pick queue or topic
                if random.choice([True, False]):
                    q_idx = random.randint(0, queue_count-1)
                    self.broker.enqueue(f'stress_q_{q_idx}', {'data': i})
                else:
                    t_idx = random.randint(0, topic_count-1)
                    self.broker.publish(f'stress_t_{t_idx}', {'data': i})
        
        threads = [threading.Thread(target=load_generator) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Wait for processing
        time.sleep(2.0)
        
        # Verify system is still responsive and metrics look reasonable
        metrics = self.broker.get_metrics()
        self.assertGreaterEqual(metrics['total_messages'], msgs_per_component * 4)
        self.assertTrue(self.broker._running)
    
    # === Admin & Monitoring Integration ===
    
    def test_admin_visibility_during_load(self):
        """Test that admin API returns correct info during active processing"""
        self.broker.create_queue('monitor_queue')
        
        # Slow worker to keep queue populated
        def slow_worker(task):
            time.sleep(0.1)
        
        self.broker.register_worker('monitor_queue', slow_worker, num_threads=2)
        self.broker.start()
        
        # Fill queue
        for i in range(20):
            self.broker.enqueue('monitor_queue', {'id': i})
        
        # Check stats immediately
        info = self.broker.get_queue_info('monitor_queue')
        
        # Should see some depth and some active workers
        # Note: Exact numbers depend on timing, but shouldn't be zero processed eventually
        self.assertEqual(info['config']['name'], 'monitor_queue')
        self.assertGreaterEqual(info['stats']['published'], 20)
        
        time.sleep(2.5)
        
        # Should be done
        stats = self.broker.get_queue_stats('monitor_queue')
        self.assertEqual(stats['processed'], 20)
        self.assertEqual(stats['depth'], 0)


if __name__ == '__main__':
    unittest.main()
