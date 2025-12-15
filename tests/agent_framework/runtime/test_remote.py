"""
Tests for remote execution components.
"""

import pytest

from agent_framework.runtime.context import ExecutionContext
from agent_framework.runtime.remote.load_balancing import (
    RoundRobinStrategy,
    LeastLoadedStrategy,
    CapabilityAwareStrategy,
    get_strategy,
)
from agent_framework.runtime.remote.pool_manager import WorkerPoolManager
from agent_framework.runtime.remote.worker import WorkerNode, WorkerStatus


class TestWorkerNode:
    """Tests for WorkerNode."""
    
    def test_create_worker(self):
        """Test creating a worker node."""
        worker = WorkerNode(
            id="worker-1",
            host="localhost",
            port=8080,
            capabilities=["gpu"],
            max_concurrent=10
        )
        
        assert worker.id == "worker-1"
        assert worker.endpoint == "http://localhost:8080"
        assert worker.capabilities == ["gpu"]
        assert worker.status == WorkerStatus.AVAILABLE
    
    def test_is_available(self):
        """Test worker availability check."""
        worker = WorkerNode(
            id="worker-1",
            host="localhost",
            port=8080,
            max_concurrent=2
        )
        
        assert worker.is_available is True
        
        worker.current_load = 2
        assert worker.is_available is False
        
        worker.current_load = 1
        worker.status = WorkerStatus.OFFLINE
        assert worker.is_available is False
    
    def test_load_percentage(self):
        """Test load percentage calculation."""
        worker = WorkerNode(
            id="worker-1",
            host="localhost",
            port=8080,
            max_concurrent=10
        )
        
        worker.current_load = 5
        assert worker.load_percentage == 50.0
        
        worker.current_load = 10
        assert worker.load_percentage == 100.0
    
    def test_has_capability(self):
        """Test capability checking."""
        worker = WorkerNode(
            id="worker-1",
            host="localhost",
            port=8080,
            capabilities=["gpu", "high-memory"]
        )
        
        assert worker.has_capability("gpu") is True
        assert worker.has_capability("cpu") is False
    
    def test_has_all_capabilities(self):
        """Test checking multiple capabilities."""
        worker = WorkerNode(
            id="worker-1",
            host="localhost",
            port=8080,
            capabilities=["gpu", "high-memory", "ssd"]
        )
        
        assert worker.has_all_capabilities(["gpu", "high-memory"]) is True
        assert worker.has_all_capabilities(["gpu", "cpu"]) is False


class TestLoadBalancingStrategies:
    """Tests for load balancing strategies."""
    
    @pytest.fixture
    def workers(self):
        """Create test workers."""
        return [
            WorkerNode(id="w1", host="host1", port=8080, current_load=2),
            WorkerNode(id="w2", host="host2", port=8080, current_load=1),
            WorkerNode(id="w3", host="host3", port=8080, current_load=3),
        ]
    
    def test_round_robin(self, workers):
        """Test round-robin strategy."""
        strategy = RoundRobinStrategy()
        
        # Should cycle through workers
        assert strategy.select_worker(workers).id == "w1"
        assert strategy.select_worker(workers).id == "w2"
        assert strategy.select_worker(workers).id == "w3"
        assert strategy.select_worker(workers).id == "w1"
    
    def test_least_loaded(self, workers):
        """Test least-loaded strategy."""
        strategy = LeastLoadedStrategy()
        
        # Should always select w2 (load=1)
        selected = strategy.select_worker(workers)
        assert selected.id == "w2"
    
    def test_capability_aware(self):
        """Test capability-aware strategy."""
        workers = [
            WorkerNode(id="w1", host="h1", port=8080, capabilities=["gpu"], current_load=2),
            WorkerNode(id="w2", host="h2", port=8080, capabilities=[], current_load=1),
            WorkerNode(id="w3", host="h3", port=8080, capabilities=["gpu", "ssd"], current_load=3),
        ]
        
        strategy = CapabilityAwareStrategy()
        
        # Should prefer w3 (most capabilities)
        selected = strategy.select_worker(workers)
        assert selected.id == "w3"
    
    def test_get_strategy(self):
        """Test getting strategy by name."""
        strategy = get_strategy("round_robin")
        assert isinstance(strategy, RoundRobinStrategy)
        
        strategy = get_strategy("least_loaded")
        assert isinstance(strategy, LeastLoadedStrategy)
    
    def test_get_unknown_strategy(self):
        """Test getting unknown strategy raises error."""
        with pytest.raises(ValueError, match="Unknown strategy"):
            get_strategy("unknown")


class TestWorkerPoolManager:
    """Tests for WorkerPoolManager."""
    
    @pytest.fixture
    def pool(self):
        """Create a worker pool."""
        return WorkerPoolManager(
            heartbeat_interval=30,
            heartbeat_timeout=90,
            load_balancing_strategy="least_loaded"
        )
    
    @pytest.fixture
    def worker(self):
        """Create a test worker."""
        return WorkerNode(
            id="test-worker",
            host="localhost",
            port=8080,
            capabilities=["gpu"]
        )
    
    @pytest.mark.asyncio
    async def test_register_worker(self, pool, worker):
        """Test registering a worker."""
        await pool.register_worker(worker)
        
        assert "test-worker" in pool.workers
        assert pool.workers["test-worker"].status == WorkerStatus.AVAILABLE
    
    @pytest.mark.asyncio
    async def test_unregister_worker(self, pool, worker):
        """Test unregistering a worker."""
        await pool.register_worker(worker)
        await pool.unregister_worker("test-worker")
        
        assert "test-worker" not in pool.workers
    
    @pytest.mark.asyncio
    async def test_select_worker(self, pool, worker):
        """Test selecting a worker."""
        await pool.register_worker(worker)
        
        selected = await pool.select_worker()
        
        assert selected is not None
        assert selected.id == "test-worker"
        assert selected.current_load == 1
    
    @pytest.mark.asyncio
    async def test_select_worker_with_capabilities(self, pool):
        """Test selecting worker with required capabilities."""
        worker1 = WorkerNode(id="w1", host="h1", port=8080, capabilities=["cpu"])
        worker2 = WorkerNode(id="w2", host="h2", port=8080, capabilities=["gpu"])
        
        await pool.register_worker(worker1)
        await pool.register_worker(worker2)
        
        selected = await pool.select_worker(required_capabilities=["gpu"])
        
        assert selected is not None
        assert selected.id == "w2"
    
    @pytest.mark.asyncio
    async def test_select_worker_exclude(self, pool):
        """Test selecting worker with exclusions."""
        worker1 = WorkerNode(id="w1", host="h1", port=8080)
        worker2 = WorkerNode(id="w2", host="h2", port=8080)
        
        await pool.register_worker(worker1)
        await pool.register_worker(worker2)
        
        selected = await pool.select_worker(exclude=["w1"])
        
        assert selected is not None
        assert selected.id == "w2"
    
    @pytest.mark.asyncio
    async def test_release_worker(self, pool, worker):
        """Test releasing a worker."""
        await pool.register_worker(worker)
        await pool.select_worker()  # Increments load
        
        assert worker.current_load == 1
        
        await pool.release_worker("test-worker")
        
        assert worker.current_load == 0
    
    @pytest.mark.asyncio
    async def test_mark_worker_failed(self, pool, worker):
        """Test marking worker as failed."""
        await pool.register_worker(worker)
        await pool.mark_worker_failed("test-worker")
        
        assert worker.status == WorkerStatus.OFFLINE
        assert worker.failed_executions == 1
    
    @pytest.mark.asyncio
    async def test_update_heartbeat(self, pool, worker):
        """Test updating worker heartbeat."""
        await pool.register_worker(worker)
        
        import time
        initial_heartbeat = worker.last_heartbeat
        time.sleep(0.1)
        
        await pool.update_heartbeat("test-worker")
        
        assert worker.last_heartbeat > initial_heartbeat
    
    @pytest.mark.asyncio
    async def test_has_available_workers(self, pool, worker):
        """Test checking for available workers."""
        assert await pool.has_available_workers() is False
        
        await pool.register_worker(worker)
        
        assert await pool.has_available_workers() is True
    
    def test_get_worker_stats(self, pool):
        """Test getting worker statistics."""
        stats = pool.get_worker_stats()
        
        assert 'total_workers' in stats
        assert 'available' in stats
        assert 'offline' in stats
