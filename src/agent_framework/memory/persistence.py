"""
Persistent Memory for Agent.
"""
import json
import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class PersistentMemory:
    """
    Key-Value store for long-term agent memory, persisted to disk.
    """
    
    def __init__(self, storage_path: str = ".agent_memory.json"):
        self.storage_path = storage_path
        self.memory: Dict[str, Any] = {}
        self.load()
        
    def load(self) -> None:
        """Load memory from disk."""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r') as f:
                    self.memory = json.load(f)
                logger.info(f"Loaded persistent memory from {self.storage_path}")
            except Exception as e:
                logger.error(f"Failed to load memory: {e}")
                self.memory = {}
        else:
            self.memory = {}
            
    def save(self) -> None:
        """Save memory to disk."""
        try:
            with open(self.storage_path, 'w') as f:
                json.dump(self.memory, f, indent=2)
            logger.info(f"Saved persistent memory to {self.storage_path}")
        except Exception as e:
            logger.error(f"Failed to save memory: {e}")
            
    def get(self, key: str) -> Optional[Any]:
        """Retrieve a value."""
        return self.memory.get(key)
        
    def set(self, key: str, value: Any) -> None:
        """Set a value and save."""
        self.memory[key] = value
        self.save()
        
    def delete(self, key: str) -> None:
        """Delete a key and save."""
        if key in self.memory:
            del self.memory[key]
            self.save()
            
    def get_all(self) -> Dict[str, Any]:
        """Get all memory items."""
        return self.memory.copy()
