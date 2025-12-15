"""
MetricsCollector - Thread-safe metrics collection and reporting.

Phase 2 implements comprehensive metrics tracking for:
- Queue metrics (published, processed, failed, dlq_count, processing time, depth, workers)
- Topic metrics (published, subscriber count, failed deliveries)
- System-wide metrics (total messages, uptime, active threads)
"""
import threading
import time
from typing import Dict, List, Any
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class QueueMetrics:
    """Metrics for a specific queue"""
    published: int = 0
    processed: int = 0
    failed: int = 0
    dlq_count: int = 0
    depth: int = 0
    worker_count: int = 0
    processing_times: List[float] = field(default_factory=list)
    
    @property
    def avg_processing_time_ms(self) -> float:
        """Calculate average processing time in milliseconds"""
        if not self.processing_times:
            return 0.0
        return sum(self.processing_times) / len(self.processing_times)


@dataclass
class TopicMetrics:
    """Metrics for a specific topic"""
    published: int = 0
    subscriber_count: int = 0
    failed_deliveries: int = 0


class MetricsCollector:
    """
    Thread-safe metrics collection for message broker.
    
    Tracks:
    - Per-queue metrics
    - Per-topic metrics
    - System-wide metrics
    """
    
    def __init__(self):
        """Initialize metrics collector"""
        self._queue_metrics: Dict[str, QueueMetrics] = defaultdict(QueueMetrics)
        self._topic_metrics: Dict[str, TopicMetrics] = defaultdict(TopicMetrics)
        
        self._lock = threading.RLock()
        self._start_time = time.time()
        self._active_threads = 0
    
    # === Queue Metrics ===
    
    def increment_queue_published(self, queue_name: str) -> None:
        """Increment published counter for a queue"""
        with self._lock:
            self._queue_metrics[queue_name].published += 1
    
    def increment_queue_processed(self, queue_name: str) -> None:
        """Increment processed counter for a queue"""
        with self._lock:
            self._queue_metrics[queue_name].processed += 1
    
    def increment_queue_failed(self, queue_name: str) -> None:
        """Increment failed counter for a queue"""
        with self._lock:
            self._queue_metrics[queue_name].failed += 1
    
    def increment_queue_dlq_count(self, queue_name: str) -> None:
        """Increment DLQ counter for a queue"""
        with self._lock:
            self._queue_metrics[queue_name].dlq_count += 1
    
    def decrement_queue_dlq_count(self, queue_name: str) -> None:
        """Decrement DLQ counter for a queue (when requeued or deleted)"""
        with self._lock:
            if self._queue_metrics[queue_name].dlq_count > 0:
                self._queue_metrics[queue_name].dlq_count -= 1
    
    def record_processing_time(self, queue_name: str, time_ms: float) -> None:
        """
        Record processing time for a queue task.
        
        Args:
            queue_name: Name of the queue
            time_ms: Processing time in milliseconds
        """
        with self._lock:
            # Keep last 1000 processing times for rolling average
            times = self._queue_metrics[queue_name].processing_times
            times.append(time_ms)
            if len(times) > 1000:
                times.pop(0)
    
    def set_queue_depth(self, queue_name: str, depth: int) -> None:
        """Set current queue depth"""
        with self._lock:
            self._queue_metrics[queue_name].depth = depth
    
    def set_worker_count(self, queue_name: str, count: int) -> None:
        """Set worker count for a queue"""
        with self._lock:
            self._queue_metrics[queue_name].worker_count = count
    
    def get_queue_stats(self, queue_name: str) -> Dict[str, Any]:
        """
        Get statistics for a specific queue.
        
        Returns:
            Dict with queue metrics
        """
        with self._lock:
            metrics = self._queue_metrics[queue_name]
            return {
                'published': metrics.published,
                'processed': metrics.processed,
                'failed': metrics.failed,
                'dlq_count': metrics.dlq_count,
                'depth': metrics.depth,
                'avg_processing_time_ms': metrics.avg_processing_time_ms,
                'worker_count': metrics.worker_count,
            }
    
    # === Topic Metrics ===
    
    def increment_topic_published(self, topic_name: str) -> None:
        """Increment published counter for a topic"""
        with self._lock:
            self._topic_metrics[topic_name].published += 1
    
    def increment_topic_failed_delivery(self, topic_name: str) -> None:
        """Increment failed delivery counter for a topic"""
        with self._lock:
            self._topic_metrics[topic_name].failed_deliveries += 1
    
    def set_subscriber_count(self, topic_name: str, count: int) -> None:
        """Set subscriber count for a topic"""
        with self._lock:
            self._topic_metrics[topic_name].subscriber_count = count
    
    def get_topic_stats(self, topic_name: str) -> Dict[str, Any]:
        """
        Get statistics for a specific topic.
        
        Returns:
            Dict with topic metrics
        """
        with self._lock:
            metrics = self._topic_metrics[topic_name]
            return {
                'published': metrics.published,
                'subscriber_count': metrics.subscriber_count,
                'failed_deliveries': metrics.failed_deliveries,
            }
    
    # === System-Wide Metrics ===
    
    def get_total_messages(self) -> int:
        """Get total messages across all queues and topics"""
        with self._lock:
            total = 0
            # Count queue messages
            for metrics in self._queue_metrics.values():
                total += metrics.published
            # Count topic messages
            for metrics in self._topic_metrics.values():
                total += metrics.published
            return total
    
    def get_uptime_seconds(self) -> float:
        """Get system uptime in seconds"""
        return time.time() - self._start_time
    
    def get_start_time(self) -> float:
        """Get start time timestamp"""
        return self._start_time
    
    def set_active_threads(self, count: int) -> None:
        """Set active thread count"""
        with self._lock:
            self._active_threads = count
    
    def get_active_threads(self) -> int:
        """Get active thread count"""
        with self._lock:
            return self._active_threads
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """
        Get complete system metrics snapshot.
        
        Returns:
            Dict with system-wide metrics
        """
        with self._lock:
            return {
                'total_messages': self.get_total_messages(),
                'uptime_seconds': self.get_uptime_seconds(),
                'active_threads': self._active_threads,
                'start_time': self._start_time,
            }
    
    # === List Operations ===
    
    def list_queues(self) -> List[str]:
        """Get list of all queues that have metrics"""
        with self._lock:
            return list(self._queue_metrics.keys())
    
    def list_topics(self) -> List[str]:
        """Get list of all topics that have metrics"""
        with self._lock:
            return list(self._topic_metrics.keys())
    
    # === Reset Operations ===
    
    def reset_queue_metrics(self, queue_name: str) -> None:
        """Reset metrics for a specific queue"""
        with self._lock:
            if queue_name in self._queue_metrics:
                self._queue_metrics[queue_name] = QueueMetrics()
    
    def reset_all_metrics(self) -> None:
        """Reset all metrics"""
        with self._lock:
            self._queue_metrics.clear()
            self._topic_metrics.clear()
            self._start_time = time.time()
            self._active_threads = 0
