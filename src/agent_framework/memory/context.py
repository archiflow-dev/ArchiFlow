"""
Context Injector for Agent.
"""
from typing import List, Optional
from ..messages.types import SystemMessage, EnvironmentMessage
from .tracker import EnvironmentTracker
from .persistence import PersistentMemory

class ContextInjector:
    """
    Aggregates context from various sources to inject into the agent's stream.
    """
    
    def __init__(
        self, 
        tracker: EnvironmentTracker, 
        memory: PersistentMemory,
        session_id: str = "default"
    ):
        self.tracker = tracker
        self.memory = memory
        self.session_id = session_id
        
    def generate_context_message(self, sequence: int) -> EnvironmentMessage:
        """
        Generate a message containing the current context.
        """
        parts = []
        
        # 1. Environment State
        parts.append(self.tracker.get_summary())
        
        # 2. Persistent Memory (Reminders)
        mem_data = self.memory.get_all()
        if mem_data:
            parts.append("\n## Persistent Memory / Reminders")
            for k, v in mem_data.items():
                parts.append(f"- **{k}**: {v}")
                
        content = "\n\n".join(parts)
        
        return EnvironmentMessage(
            session_id=self.session_id,
            sequence=sequence,
            event_type="context_update",
            content=content
        )
