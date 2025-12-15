"""
Tests for PersistentMemory.
"""
import pytest
import os
import tempfile
from src.agent_framework.memory.persistence import PersistentMemory

def test_persistent_memory_initialization():
    """Test memory initializes empty."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        temp_path = f.name
    
    try:
        memory = PersistentMemory(storage_path=temp_path)
        assert isinstance(memory.memory, dict)
        assert len(memory.memory) == 0
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

def test_set_and_get():
    """Test setting and getting values."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        temp_path = f.name
    
    try:
        memory = PersistentMemory(storage_path=temp_path)
        memory.set("test_key", "test_value")
        
        assert memory.get("test_key") == "test_value"
        assert memory.get("nonexistent") is None
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

def test_persistence_across_instances():
    """Test that data persists across instances."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        temp_path = f.name
    
    try:
        # First instance
        memory1 = PersistentMemory(storage_path=temp_path)
        memory1.set("persistent", "data")
        
        # Second instance should load the data
        memory2 = PersistentMemory(storage_path=temp_path)
        assert memory2.get("persistent") == "data"
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

def test_delete():
    """Test deleting keys."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        temp_path = f.name
    
    try:
        memory = PersistentMemory(storage_path=temp_path)
        memory.set("to_delete", "value")
        assert memory.get("to_delete") == "value"
        
        memory.delete("to_delete")
        assert memory.get("to_delete") is None
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

def test_get_all():
    """Test retrieving all memory items."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        temp_path = f.name
    
    try:
        memory = PersistentMemory(storage_path=temp_path)
        memory.set("key1", "value1")
        memory.set("key2", "value2")
        
        all_items = memory.get_all()
        assert all_items == {"key1": "value1", "key2": "value2"}
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
