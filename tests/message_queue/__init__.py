"""Test package for event_queue message broker system.

This package contains comprehensive unit and integration tests organized by implementation phase:

Phase 1 (test_phase1_core.py): Core Message and Broker components
Phase 2 (test_phase2_metrics.py): Metrics Collection and Management
Phase 3 (test_phase3_pubsub.py): Pub/Sub with Threading and Async Support
Phase 4 (test_phase4_workers.py): Worker/Task Queue System
Phase 5 (test_phase5_dlq.py): Dead Letter Queue (DLQ) System
Phase 6 (test_phase6_admin.py): Admin API
Phase 7 (test_phase7_lifecycle.py): Lifecycle and Thread Management
Phase 8 (test_phase8_integration.py): Integration Tests

Run all tests:
    python -m unittest discover tests

Run specific phase:
    python -m unittest tests.test_phase1_core
    python -m unittest tests.test_phase3_pubsub
    
Run with verbose output:
    python -m unittest discover tests -v
"""

__all__ = [
    'test_phase1_core',
    'test_phase2_metrics',
    'test_phase3_pubsub',
    'test_phase4_workers',
    'test_phase5_dlq',
    'test_phase6_admin',
    'test_phase7_lifecycle',
    'test_phase8_integration',
]
