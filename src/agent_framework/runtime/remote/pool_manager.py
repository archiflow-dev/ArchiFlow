"""
Worker pool manager for managing remote worker nodes.

This module provides the WorkerPoolManager class that handles
worker registration, health monitoring, and selection.
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Set

from agent_framework.runtime.remote.load_balancing import (
    LoadBalancingStrategy,
    get_strategy,
)
from agent_framework.runtime.remote.worker import WorkerNode, WorkerStatus

logger = logging.getLogger(__name__)


class WorkerPoolManager:
    """
    Manages pool of remote worker nodes.
    
    Features:
    - Worker registration and unregistration
    - Health monitoring via heartbeats
    - Worker selection with load balancing
    - Automatic failover for offline workers
    """
    
    def __init__(
        self,
        heartbeat_interval: int = 30,
        heartbeat_timeout: int = 90,
        load_balancing_strategy: str = "least_loaded"
    ):
        """
        Initialize the worker pool manager.
        
        Args:
            heartbeat_interval: Seconds between health checks
            heartbeat_timeout: Seconds before marking worker offline
            load_balancing_strategy: Strategy name for worker selection
        """
        self.workers: Dict[str, WorkerNode] = {}
        self.heartbeat_interval = heartbeat_interval
        self.heartbeat_timeout = heartbeat_timeout
        self.strategy = get_strategy(load_balancing_strategy)
        
        self._lock = asyncio.Lock()
        self._health_monitor_task: Optional[asyncio.Task] = None
        
        logger.info(
            "WorkerPoolManager initialized (strategy=%s, heartbeat=%ds)",
            load_balancing_strategy,
            heartbeat_interval
        )
    
    async def register_worker(self, worker: WorkerNode) -> None:
        """
        Register a new worker node.
        
        Args:
            worker: Worker to register
        """
        async with self._lock:
            worker.last_heartbeat = time.time()
            worker.status = WorkerStatus.AVAILABLE
            self.workers[worker.id] = worker
            
            logger.info(
                f"Registered worker: {worker.id} at {worker.endpoint} "
                f"(capabilities: {worker.capabilities})"
            )
    
    async def unregister_worker(self, worker_id: str) -> None:
        """
        Unregister a worker node.
        
        Args:
            worker_id: ID of worker to unregister
        """
        async with self._lock:
            if worker_id in self.workers:
                worker = self.workers[worker_id]
                del self.workers[worker_id]
                logger.info(f"Unregistered worker: {worker_id}")
    
    async def select_worker(
        self,
        required_capabilities: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None
    ) -> Optional[WorkerNode]:
        """
        Select best available worker using load balancing.
        
        Args:
            required_capabilities: Required worker capabilities
            exclude: Worker IDs to exclude from selection
            
        Returns:
            Selected worker or None if no suitable worker found
        """
        async with self._lock:
            candidates = []
            
            for worker in self.workers.values():
                # Skip excluded workers
                if exclude and worker.id in exclude:
                    continue
                
                # Check availability
                if not worker.is_available:
                    continue
                
                # Check capabilities
                if required_capabilities:
                    if not worker.has_all_capabilities(required_capabilities):
                        continue
                
                candidates.append(worker)
            
            if not candidates:
                logger.warning(
                    f"No available workers found "
                    f"(required_capabilities={required_capabilities})"
                )
                return None
            
            # Select worker using strategy
            selected = self.strategy.select_worker(candidates)
            
            if selected:
                selected.current_load += 1
                logger.debug(
                    f"Selected worker {selected.id} "
                    f"(load: {selected.current_load}/{selected.max_concurrent})"
                )
            
            return selected
    
    async def release_worker(self, worker_id: str) -> None:
        """
        Release worker after execution completes.
        
        Args:
            worker_id: ID of worker to release
        """
        async with self._lock:
            if worker_id in self.workers:
                worker = self.workers[worker_id]
                worker.current_load = max(0, worker.current_load - 1)
                
                logger.debug(
                    f"Released worker {worker_id} "
                    f"(load: {worker.current_load}/{worker.max_concurrent})"
                )
    
    async def mark_worker_failed(self, worker_id: str) -> None:
        """
        Mark worker as failed/offline.
        
        Args:
            worker_id: ID of worker that failed
        """
        async with self._lock:
            if worker_id in self.workers:
                worker = self.workers[worker_id]
                worker.status = WorkerStatus.OFFLINE
                worker.failed_executions += 1
                
                logger.warning(f"Marked worker as offline: {worker_id}")
    
    async def update_heartbeat(self, worker_id: str) -> None:
        """
        Update worker heartbeat timestamp.
        
        Args:
            worker_id: ID of worker
        """
        async with self._lock:
            if worker_id in self.workers:
                worker = self.workers[worker_id]
                worker.last_heartbeat = time.time()
                
                # Restore to available if was offline
                if worker.status == WorkerStatus.OFFLINE:
                    worker.status = WorkerStatus.AVAILABLE
                    logger.info(f"Worker {worker_id} back online")
    
    async def has_available_workers(self) -> bool:
        """
        Check if any workers are available.
        
        Returns:
            True if at least one worker is available
        """
        async with self._lock:
            return any(w.is_available for w in self.workers.values())
    
    def start_health_monitoring(self) -> None:
        """Start background health monitoring."""
        if not self._health_monitor_task:
            self._health_monitor_task = asyncio.create_task(
                self._health_monitor_loop()
            )
            logger.info("Started health monitoring")
    
    async def stop_health_monitoring(self) -> None:
        """Stop health monitoring."""
        if self._health_monitor_task:
            self._health_monitor_task.cancel()
            try:
                await self._health_monitor_task
            except asyncio.CancelledError:
                pass
            self._health_monitor_task = None
            logger.info("Stopped health monitoring")
    
    async def _health_monitor_loop(self) -> None:
        """Background task to monitor worker health."""
        while True:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                await self._check_worker_health()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health monitor error: {e}", exc_info=True)
    
    async def _check_worker_health(self) -> None:
        """Check health of all workers."""
        current_time = time.time()
        
        async with self._lock:
            for worker in self.workers.values():
                time_since_heartbeat = current_time - worker.last_heartbeat
                
                if time_since_heartbeat > self.heartbeat_timeout:
                    if worker.status != WorkerStatus.OFFLINE:
                        worker.status = WorkerStatus.OFFLINE
                        logger.warning(
                            f"Worker timeout: {worker.id} "
                            f"(last heartbeat: {time_since_heartbeat:.0f}s ago)"
                        )
    
    def get_worker_stats(self) -> Dict[str, Any]:
        """
        Get statistics about worker pool.
        
        Returns:
            Dictionary with statistics
        """
        total = len(self.workers)
        available = sum(1 for w in self.workers.values() if w.is_available)
        busy = sum(1 for w in self.workers.values() if w.status == WorkerStatus.BUSY)
        offline = sum(1 for w in self.workers.values() if w.status == WorkerStatus.OFFLINE)
        
        return {
            'total_workers': total,
            'available': available,
            'busy': busy,
            'offline': offline,
            'total_load': sum(w.current_load for w in self.workers.values()),
            'total_executions': sum(w.total_executions for w in self.workers.values()),
            'total_failures': sum(w.failed_executions for w in self.workers.values())
        }
    
    def get_workers(self) -> List[WorkerNode]:
        """
        Get list of all workers.
        
        Returns:
            List of worker nodes
        """
        return list(self.workers.values())
