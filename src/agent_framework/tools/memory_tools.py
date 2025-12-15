"""
Memory tools for agent persistent storage.
"""
from typing import Optional
from .tool_base import tool

@tool(name="remember", description="Store information in persistent memory for later recall")
def remember(key: str, value: str) -> str:
    """
    Store a key-value pair in persistent memory.
    
    Args:
        key: The identifier for the memory
        value: The information to store
        
    Returns:
        Confirmation message
    """
    # This will be called by the agent, which should inject the persistent_memory instance
    # For now, we return a placeholder. The actual implementation will use the agent's memory.
    return f"Remembered: {key} = {value}"

@tool(name="recall", description="Retrieve information from persistent memory")
def recall(key: str) -> str:
    """
    Retrieve a value from persistent memory.
    
    Args:
        key: The identifier for the memory
        
    Returns:
        The stored value or an error message
    """
    # This will be called by the agent, which should inject the persistent_memory instance
    # For now, we return a placeholder
    return f"Attempting to recall: {key}"
