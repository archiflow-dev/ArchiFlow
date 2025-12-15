"""
MessageBroker - Core message broker implementation.

Phases implemented:
- Phase 1: Basic structure with subscribe/unsubscribe
- Phase 2: Metrics integration
- Phase 3: Pub/Sub with threading and async support
- Phase 4: Worker/Task Queue system
- Phase 2 (Persistence): Refactored to use StorageBackend
"""
import logging
import threading
import queue
import time
import asyncio
import inspect
from typing import Dict, List, Any, Optional, Callable, Union

from .message import Message, QueueConfig
from .metrics import MetricsCollector
from .exceptions import (
    QueueNotFoundError, 
    QueueAlreadyExistsError, 
    InvalidCallbackError,
    BrokerNotRunningError,
    MessageNotFoundError
)
from .storage import StorageBackend, InMemoryBackend

# Configure logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

class MessageBroker:
    """
    Central message broker managing pub/sub and task queues.
    Delegates storage to a pluggable backend.
    """
    
    def __init__(self, storage_backend: Optional[StorageBackend] = None):
        """
        Initialize the message broker.
        
        Args:
            storage_backend: Optional storage backend. Defaults to InMemoryBackend.
        """
        # Pub/Sub (Phase 3) - kept in-memory as per design (lightweight)
        self._subscriptions: Dict[str, List[Callable]] = {}
        self._subscription_queues: Dict[str, queue.Queue] = {}
        self._subscription_threads: Dict[str, threading.Thread] = {}
        
        # Storage Backend (Phase 2 Refactor)
        self._storage = storage_backend or InMemoryBackend()
        self._storage.initialize()
        
        # Configuration & Workers
        self._queue_configs: Dict[str, QueueConfig] = {}
        self._workers: Dict[str, List[threading.Thread]] = {}
        self._worker_callbacks: Dict[str, Callable] = {}
        self._worker_thread_counts: Dict[str, int] = {}
        
        # Metrics (Phase 2)
        self._metrics = MetricsCollector()
        
        # Thread safety
        self._lock = threading.RLock()
        self._running = False
        
        # Async support
        self._event_loop: Optional[asyncio.AbstractEventLoop] = None
        self._event_loop_thread: Optional[threading.Thread] = None
        self._has_async_callbacks = True
    
    # === Compatibility Properties for Tests ===
    # These expose storage internals for backward compatibility with existing tests
    
    @property
    def _queues(self) -> Dict[str, Any]:
        """Compatibility property for tests accessing internal queues."""
        if hasattr(self._storage, '_queues'):
            return self._storage._queues
        return {}
    
    @property
    def _dlqs(self) -> Dict[str, List[Message]]:
        """Compatibility property for tests accessing internal DLQs."""
        if hasattr(self._storage, '_dlqs'):
            # Filter to only return DLQs for queues with dlq_enabled=True
            filtered_dlqs = {}
            for queue_name, dlq in self._storage._dlqs.items():
                if queue_name in self._queue_configs and self._queue_configs[queue_name].dlq_enabled:
                    filtered_dlqs[queue_name] = dlq
            return filtered_dlqs
        return {}
    
    # === Pub/Sub Methods (Phase 3) ===
    
    def subscribe(self, topic: str, callback: Callable) -> None:
        """Register a subscriber callback for a topic."""
        if not topic:
            raise ValueError("Topic name cannot be empty")
        if callback is None:
            raise TypeError("Callback cannot be None")
        if not callable(callback):
            raise TypeError(f"Callback must be callable, got {type(callback)}")
        
        with self._lock:
            if topic not in self._subscriptions:
                self._subscriptions[topic] = []
                self._subscription_queues[topic] = queue.Queue()
            
            self._subscriptions[topic].append(callback)
            
            if asyncio.iscoroutinefunction(callback):
                self._has_async_callbacks = True
            
            self._metrics.set_subscriber_count(topic, len(self._subscriptions[topic]))
            
            if self._running and topic not in self._subscription_threads:
                self._start_topic_delivery_thread(topic)
    
    def unsubscribe(self, topic: str, callback: Callable) -> None:
        """Remove a subscriber callback from a topic."""
        with self._lock:
            if topic in self._subscriptions:
                if callback in self._subscriptions[topic]:
                    self._subscriptions[topic].remove(callback)
                    self._metrics.set_subscriber_count(topic, len(self._subscriptions[topic]))
                    
                    if not self._subscriptions[topic]:
                        del self._subscriptions[topic]
                        if topic in self._subscription_threads:
                            self._subscription_queues[topic].put(None)
    
    def publish(self, topic: str, payload: Any, metadata: Optional[Dict[str, Any]] = None) -> Message:
        """Publish a message to a topic."""
        if not topic:
            raise ValueError("Topic name cannot be empty")
        
        message = Message.create(topic=topic, payload=payload, metadata=metadata)
        self._metrics.increment_topic_published(topic)
        if self._running and topic in self._subscriptions:
            self._subscription_queues[topic].put(message)
        
        return message

    def broadcast(self, topics: List[str], payload: Any, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Message]:
        """
        Publish the same payload to multiple topics.
        
        Args:
            topics: List of topic names to publish to.
            payload: The message payload.
            metadata: Optional metadata.
            
        Returns:
            Dict mapping topic names to the created Message objects.
            
        Raises:
            ValueError: If topics list is empty.
        """
        if not topics:
            raise ValueError("Topics list cannot be empty")
            
        results = {}
        for topic in topics:
            # Reuse publish logic for consistency
            results[topic] = self.publish(topic, payload, metadata)
            
        return results
    
    def _start_topic_delivery_thread(self, topic: str) -> None:
        """Start a delivery thread for a specific topic."""
        def delivery_worker():
            while self._running:
                try:
                    try:
                        message = self._subscription_queues[topic].get(timeout=0.1)
                    except queue.Empty:
                        continue
                    
                    if message is None:
                        break
                    
                    with self._lock:
                        callbacks = self._subscriptions.get(topic, []).copy()
                    for callback in callbacks:
                        try:
                            if asyncio.iscoroutinefunction(callback):
                                if self._event_loop and self._event_loop.is_running():
                                    asyncio.run_coroutine_threadsafe(callback(message), self._event_loop)
                                else:
                                    asyncio.run(callback(message))
                            else:
                                callback(message)
                        except Exception as e:
                            logger.error(f"Error in subscriber for topic '{topic}': {e}")
                            self._metrics.increment_topic_failed_delivery(topic)
                
                except Exception as e:
                    logger.error(f"Error in delivery worker for topic '{topic}': {e}")
        
        thread = threading.Thread(target=delivery_worker, daemon=True, name=f"delivery-{topic}")
        thread.start()
        self._subscription_threads[topic] = thread
    
    # === Worker Queue Methods (Phase 4) ===
    
    def create_queue(self, queue_name: str, max_retries: int = 3, dlq_enabled: bool = True) -> None:
        """
        Create a task queue.
        """
        if not queue_name:
            raise ValueError("Queue name cannot be empty")
        
        with self._lock:
            if queue_name in self._queue_configs:
                raise QueueAlreadyExistsError(f"Queue '{queue_name}' already exists")
            
            config = QueueConfig(
                name=queue_name,
                max_retries=max_retries,
                dlq_enabled=dlq_enabled
            )
            self._queue_configs[queue_name] = config
            
            # Delegate to storage
            self._storage.create_queue(queue_name)
    
    def enqueue(self, queue_name: str, task: Any, metadata: Optional[Dict[str, Any]] = None) -> Message:
        """
        Enqueue a task to a worker queue.
        """
        if queue_name not in self._queue_configs:
            raise QueueNotFoundError(f"Queue '{queue_name}' does not exist")
        
        config = self._queue_configs[queue_name]
        message = Message.create(
            topic=queue_name,
            payload=task,
            max_retries=config.max_retries,
            metadata=metadata
        )
        
        # Delegate to storage
        self._storage.enqueue(queue_name, message)
        
        self._metrics.increment_queue_published(queue_name)
        self._metrics.set_queue_depth(queue_name, self._storage.get_queue_depth(queue_name))
        
        return message
    
    def register_worker(self, queue_name: str, worker: Callable, num_threads: int = 1) -> None:
        """
        Register worker(s) for a queue.
        """
        if queue_name not in self._queue_configs:
            raise QueueNotFoundError(f"Queue '{queue_name}' does not exist")
        
        if worker is None:
            raise TypeError("Worker cannot be None")
        
        if not callable(worker):
            raise TypeError(f"Worker must be callable, got {type(worker)}")
        
        if num_threads <= 0:
            raise ValueError("num_threads must be positive")
        
        with self._lock:
            self._worker_callbacks[queue_name] = worker
            self._worker_thread_counts[queue_name] = num_threads
            
            if asyncio.iscoroutinefunction(worker):
                self._has_async_callbacks = True
            
            # Start worker threads if broker is running
            if self._running:
                self._start_worker_threads(queue_name, num_threads)
            else:
                # Store thread count for later
                if queue_name not in self._workers:
                    self._workers[queue_name] = []
    
    def _start_worker_threads(self, queue_name: str, num_threads: int) -> None:
        """Start worker threads for a queue."""
        worker_func = self._worker_callbacks[queue_name]
        config = self._queue_configs[queue_name]
        
        def worker_thread():
            """Worker thread that processes tasks from queue."""
            # Create a dedicated event loop for this worker thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                while self._running:
                    try:
                        # Dequeue from storage with timeout
                        message = self._storage.dequeue(queue_name, timeout=0.1)
                        
                        if message is None:
                            continue
                        
                        # Update queue depth
                        self._metrics.set_queue_depth(queue_name, self._storage.get_queue_depth(queue_name))
                        
                        # Process the task
                        start_time = time.time()
                        success = False
                        
                        try:
                            if asyncio.iscoroutinefunction(worker_func):
                                # Async worker - run in this thread's persistent loop
                                loop.run_until_complete(worker_func(message.payload))
                            else:
                                # Sync worker
                                worker_func(message.payload)
                            
                            success = True
                            
                        except Exception as e:
                            # Task failed
                            message.retry_count += 1
                            message.error = str(e)
                            logger.error(f"Worker error in queue '{queue_name}': {e}")
                        
                        # Record processing time
                        processing_time_ms = (time.time() - start_time) * 1000
                        self._metrics.record_processing_time(queue_name, processing_time_ms)
                        
                        if success:
                            # Task succeeded
                            self._storage.ack(queue_name, message.id)
                            self._metrics.increment_queue_processed(queue_name)
                        else:
                            # Task failed - check if we should retry
                            if message.retry_count <= message.max_retries:
                                # Retry - nack will requeue
                                self._storage.nack(queue_name, message.id)
                            else:
                                # Max retries exceeded - move to DLQ if enabled
                                self._metrics.increment_queue_failed(queue_name)
                                
                                if config.dlq_enabled:
                                    self._storage.move_to_dlq(queue_name, message)
                                    self._storage.ack(queue_name, message.id)
                                    self._metrics.increment_queue_dlq_count(queue_name)
                                else:
                                    # Just drop it (ack removes it)
                                    self._storage.ack(queue_name, message.id)
                    
                    except Exception as e:
                        logger.error(f"Error in worker thread for queue '{queue_name}': {e}")
            finally:
                # Clean up the loop when thread exits
                loop.close()
        
        # Create and start worker threads
        for i in range(num_threads):
            thread = threading.Thread(
                target=worker_thread,
                daemon=True,
                name=f"worker-{queue_name}-{i}"
            )
            thread.start()
            self._workers.setdefault(queue_name, []).append(thread)
        
        # Update metrics
        self._metrics.set_worker_count(queue_name, len(self._workers[queue_name]))
    
    # === Event Loop Management ===
    
    def _start_event_loop(self) -> None:
        """Start event loop in a dedicated thread for async callbacks"""
        if self._event_loop_thread is not None:
            return
        
        def run_event_loop():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._event_loop = loop
            loop.run_forever()
        
        self._event_loop_thread = threading.Thread(target=run_event_loop, daemon=True, name="event-loop")
        self._event_loop_thread.start()
        
        while self._event_loop is None:
            pass
    
    def _stop_event_loop(self) -> None:
        """Stop the event loop thread"""
        if self._event_loop and self._event_loop.is_running():
            self._event_loop.call_soon_threadsafe(self._event_loop.stop)
        
        if self._event_loop_thread:
            self._event_loop_thread.join(timeout=1.0)
            self._event_loop_thread = None
            self._event_loop = None
    
    # === Lifecycle Methods ===
    
    def start(self) -> None:
        """Start the message broker."""
        with self._lock:
            if self._running:
                return
            
            self._running = True
            
            # Start event loop if we have async callbacks
            if self._has_async_callbacks:
                self._start_event_loop()
            
            # Start delivery threads for all topics
            for topic in self._subscriptions.keys():
                if topic not in self._subscription_threads:
                    self._start_topic_delivery_thread(topic)
            
            # Start worker threads for all queues with registered workers
            for queue_name, worker_func in self._worker_callbacks.items():
                if queue_name not in self._workers or not self._workers[queue_name]:
                    # Use stored thread count or default to 1
                    num_threads = self._worker_thread_counts.get(queue_name, 1)
                    self._start_worker_threads(queue_name, num_threads)
    
    def stop(self, timeout: float = 5.0) -> None:
        """Stop the message broker."""
        # 1. Signal shutdown and collect threads to join
        threads_to_join = []
        worker_threads_to_join = []
        
        with self._lock:
            if not self._running:
                return
            
            self._running = False
            
            # Collect topic threads
            for thread in self._subscription_threads.values():
                if thread.is_alive():
                    threads_to_join.append(thread)
            
            # Collect worker threads
            for threads in self._workers.values():
                for thread in threads:
                    if thread.is_alive():
                        worker_threads_to_join.append(thread)
        
        # 2. Stop event loop (handles its own thread joining safely?)
        # _stop_event_loop doesn't use the lock, but let's be careful.
        # It joins _event_loop_thread.
        self._stop_event_loop()
        
        # 3. Join threads (OUTSIDE the lock)
        for thread in threads_to_join:
            thread.join(timeout=timeout)
        self._subscription_threads.clear()
        
        for thread in worker_threads_to_join:
            thread.join(timeout=timeout)
        self._workers.clear()
        
        # 4. Close storage
        self._storage.close()
            
    # === DLQ Management (Phase 5) ===
    
    def get_dlq_messages(self, queue_name: str) -> List[Message]:
        """Get all messages in the Dead Letter Queue."""
        if queue_name not in self._queue_configs:
            raise QueueNotFoundError(f"Queue '{queue_name}' does not exist")
        
        return self._storage.get_dlq_messages(queue_name)
    
    def requeue_from_dlq(self, queue_name: str, message_id: str) -> None:
        """Move a message from DLQ back to the main queue."""
        if queue_name not in self._queue_configs:
            raise QueueNotFoundError(f"Queue '{queue_name}' does not exist")
            
        # Storage handles the move
        self._storage.requeue_from_dlq(queue_name, message_id)
        
        # Update metrics
        self._metrics.increment_queue_published(queue_name)
        self._metrics.set_queue_depth(queue_name, self._storage.get_queue_depth(queue_name))
        self._metrics.decrement_queue_dlq_count(queue_name)
    
    def delete_dlq_message(self, queue_name: str, message_id: str) -> None:
        """Permanently delete a message from the DLQ."""
        if queue_name not in self._queue_configs:
            raise QueueNotFoundError(f"Queue '{queue_name}' does not exist")
            
        self._storage.delete_dlq_message(queue_name, message_id)
        self._metrics.decrement_queue_dlq_count(queue_name)

    # === Admin API (Phase 6) ===
    
    def list_queues(self) -> List[str]:
        """List all active queues."""
        return list(self._queue_configs.keys())
    
    def list_topics(self) -> List[str]:
        """List all topics."""
        metrics = self._metrics.get_system_metrics()
        topic_keys = metrics.get('topics', {}).keys() if 'topics' in metrics else []
        return sorted(list(set(list(self._subscriptions.keys()) + list(topic_keys))))
    
    def list_subscription_queues_for_topic(self, topic: str) -> List[str]:
        """List all active subscription queues for a topic."""
        subscription_queue = self._subscription_queues.get(topic)
        if subscription_queue:
            import copy
            queue_copy = copy.copy(subscription_queue)
            lst = []
            while not queue_copy.empty():
                lst.append(queue_copy.get())
            return lst
        return []

    def purge_queue(self, queue_name: str) -> int:
        """Remove all messages from a queue."""
        if queue_name not in self._queue_configs:
            raise QueueNotFoundError(f"Queue '{queue_name}' does not exist")
        
        # Get count before deleting
        try:
            count = self._storage.get_queue_depth(queue_name)
        except QueueNotFoundError:
            count = 0
            
        self._storage.delete_queue(queue_name)
        self._storage.create_queue(queue_name)
        
        self._metrics.set_queue_depth(queue_name, 0)
        return count
    
    def get_queue_info(self, queue_name: str) -> Dict[str, Any]:
        """Get configuration and stats for a queue."""
        if queue_name not in self._queue_configs:
            raise QueueNotFoundError(f"Queue '{queue_name}' does not exist")
        
        config = self._queue_configs[queue_name]
        stats = self.get_queue_stats(queue_name)
        
        return {
            'config': {
                'name': config.name,
                'max_retries': config.max_retries,
                'dlq_enabled': config.dlq_enabled
            },
            'stats': stats
        }

    def get_queue_stats(self, queue_name: str) -> Dict[str, Any]:
        """Get statistics for a specific queue."""
        return self._metrics.get_queue_stats(queue_name)
    
    def get_topic_stats(self, topic: str) -> Dict[str, Any]:
        """Get statistics for a specific topic."""
        return self._metrics.get_topic_stats(topic)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get system-wide metrics."""
        return self._metrics.get_system_metrics()
