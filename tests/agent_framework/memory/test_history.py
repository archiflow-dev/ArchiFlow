"""
Tests for HistoryManager.
"""
import pytest
from src.agent_framework.memory.history import HistoryManager
from src.agent_framework.memory.summarizer import SimpleSummarizer
from src.agent_framework.messages.types import (
    SystemMessage, UserMessage, ToolCallMessage, ToolResultObservation
)

def test_history_compaction_selective_retention():
    """Test that compaction keeps Head (System+Goal) and Tail (N), summarizing Middle."""
    history = HistoryManager(
        max_tokens=10,
        retention_window=2,
        summarizer=SimpleSummarizer()
    ) # Very low max_tokens to force compaction
    
    # 1. System Message (Head)
    sys_msg = SystemMessage(content="System Prompt", session_id="test", sequence=0)
    history.add(sys_msg)
    
    # 2. User Goal (Head)
    goal_msg = UserMessage(content="My Goal", session_id="test", sequence=1)
    history.add(goal_msg)
    
    # 3. Middle Messages (Should be compacted)
    for i in range(5):
        history.add(UserMessage(content=f"Middle {i}", session_id="test", sequence=2+i))
        
    # 4. Tail Messages (Should be kept)
    tail1 = UserMessage(content="Tail 1", session_id="test", sequence=10)
    history.add(tail1)
    tail2 = UserMessage(content="Tail 2", session_id="test", sequence=11)
    history.add(tail2)
    
    # Trigger compaction manually or ensure it ran
    # With max_tokens=10, it should have run multiple times.
    # Let's force one last check
    history.compact()
    
    msgs = history.get_messages()
    
    # Expected structure:
    # [System, Goal, Summary, Tail1, Tail2]

    assert len(msgs) == 5
    assert msgs[0] == sys_msg
    assert msgs[1] == goal_msg
    assert isinstance(msgs[2], SystemMessage)
    assert "Compacted" in msgs[2].content
    assert msgs[3] == tail1
    assert msgs[4] == tail2

def test_token_estimation():
    history = HistoryManager(summarizer=SimpleSummarizer())
    history.add(UserMessage(content="Hello", session_id="test", sequence=0))
    # "Hello" is 5 chars -> ~1 token
    assert history.get_token_estimate() >= 1
