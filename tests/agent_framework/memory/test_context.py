"""
Tests for ContextInjector.
"""
import pytest
import tempfile
from src.agent_framework.memory.context import ContextInjector
from src.agent_framework.memory.tracker import EnvironmentTracker
from src.agent_framework.memory.persistence import PersistentMemory

def test_context_injector_initialization():
    """Test context injector initializes."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        temp_path = f.name
    
    tracker = EnvironmentTracker()
    memory = PersistentMemory(storage_path=temp_path)
    injector = ContextInjector(tracker, memory, "test_session")
    
    assert injector.session_id == "test_session"
    assert injector.tracker is tracker
    assert injector.memory is memory

def test_generate_context_message():
    """Test context message generation."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        temp_path = f.name
    
    tracker = EnvironmentTracker()
    tracker.cwd = "/workspace"
    
    memory = PersistentMemory(storage_path=temp_path)
    memory.set("user_pref", "use_pytest")
    
    injector = ContextInjector(tracker, memory, "test_session")
    msg = injector.generate_context_message(sequence=1)
    
    assert msg.session_id == "test_session"
    assert msg.sequence == 1
    assert "/workspace" in msg.content
    assert "user_pref" in msg.content
    assert "use_pytest" in msg.content
