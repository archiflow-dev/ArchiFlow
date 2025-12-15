"""
Load balancing strategies for worker selection.

This module defines different strategies for selecting workers
from the pool based on various criteria.
"""

import random
from abc import ABC, abstractmethod
from typing import List, Optional

from agent_framework.runtime.remote.worker import WorkerNode


class LoadBalancingStrategy(ABC):
    """Base class for load balancing strategies."""
    
    @abstractmethod
    def select_worker(self, workers: List[WorkerNode]) -> Optional[WorkerNode]:
        """
        Select a worker from available workers.
        
        Args:
            workers: List of available workers
            
        Returns:
            Selected worker or None if no workers available
        """
        pass


class RoundRobinStrategy(LoadBalancingStrategy):
    """
    Round-robin load balancing.
    
    Distributes requests evenly across workers in rotation.
    """
    
    def __init__(self):
        """Initialize round-robin strategy."""
        self.current_index = 0
    
    def select_worker(self, workers: List[WorkerNode]) -> Optional[WorkerNode]:
        """Select next worker in round-robin fashion."""
        if not workers:
            return None
        
        worker = workers[self.current_index % len(workers)]
        self.current_index += 1
        return worker


class LeastLoadedStrategy(LoadBalancingStrategy):
    """
    Least-loaded load balancing.
    
    Selects the worker with the lowest current load.
    """
    
    def select_worker(self, workers: List[WorkerNode]) -> Optional[WorkerNode]:
        """Select worker with lowest current load."""
        if not workers:
            return None
        
        return min(workers, key=lambda w: w.current_load)


class CapabilityAwareStrategy(LoadBalancingStrategy):
    """
    Capability-aware load balancing.
    
    Prefers workers with more capabilities, then selects by lowest load.
    """
    
    def select_worker(self, workers: List[WorkerNode]) -> Optional[WorkerNode]:
        """Select worker based on capabilities and load."""
        if not workers:
            return None
        
        # Sort by number of capabilities (descending), then by load (ascending)
        return min(
            workers,
            key=lambda w: (-len(w.capabilities), w.current_load)
        )


class RandomStrategy(LoadBalancingStrategy):
    """
    Random load balancing.
    
    Randomly selects a worker from available workers.
    """
    
    def select_worker(self, workers: List[WorkerNode]) -> Optional[WorkerNode]:
        """Randomly select a worker."""
        if not workers:
            return None
        
        return random.choice(workers)


class WeightedLoadStrategy(LoadBalancingStrategy):
    """
    Weighted load balancing.
    
    Selects workers based on their capacity and current load,
    giving preference to workers with more available capacity.
    """
    
    def select_worker(self, workers: List[WorkerNode]) -> Optional[WorkerNode]:
        """Select worker with most available capacity."""
        if not workers:
            return None
        
        # Calculate available capacity for each worker
        def available_capacity(worker: WorkerNode) -> int:
            return worker.max_concurrent - worker.current_load
        
        return max(workers, key=available_capacity)


def get_strategy(strategy_name: str) -> LoadBalancingStrategy:
    """
    Get a load balancing strategy by name.
    
    Args:
        strategy_name: Name of the strategy
        
    Returns:
        LoadBalancingStrategy instance
        
    Raises:
        ValueError: If strategy name is unknown
    """
    strategies = {
        "round_robin": RoundRobinStrategy,
        "least_loaded": LeastLoadedStrategy,
        "capability_aware": CapabilityAwareStrategy,
        "random": RandomStrategy,
        "weighted": WeightedLoadStrategy,
    }
    
    strategy_class = strategies.get(strategy_name.lower())
    if strategy_class is None:
        raise ValueError(
            f"Unknown strategy: {strategy_name}. "
            f"Available: {', '.join(strategies.keys())}"
        )
    
    return strategy_class()
