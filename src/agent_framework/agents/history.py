"""
Conversation History Management.

Maintains chronological history of messages and converts to LLM API format.
"""
import logging
import json
from typing import List, Dict, Any
from ..messages.types import (
    BaseMessage, UserMessage, SystemMessage, LLMThinkMessage,
    LLMRespondMessage, ToolCallMessage, ToolResultObservation,
    ErrorObservation, EnvironmentMessage
)

logger = logging.getLogger(__name__)


class ConversationHistory:
    """Manages conversation history for an agent session."""
    
    def __init__(self):
        self.messages: List[BaseMessage] = []
    
    def add(self, message: BaseMessage) -> None:
        """Add a message to history."""
        self.messages.append(message)
    
    def get_recent(self, n: int) -> List[BaseMessage]:
        """Get the last N messages."""
        return self.messages[-n:] if n > 0 else []
    
    def to_llm_format(self) -> List[Dict[str, Any]]:
        """
        Convert conversation history to LLM API format (OpenAI-style).

        Returns list of dicts with 'role' and 'content' fields.
        """
        llm_messages = []

        logger.debug(f"Converting {len(self.messages)} messages to LLM format")

        for i, msg in enumerate(self.messages):
            logger.debug(f"Message {i}: {type(msg).__name__}, content={repr(getattr(msg, 'content', 'N/A'))}")
            if isinstance(msg, UserMessage):
                llm_messages.append({
                    "role": "user",
                    "content": msg.content or ""  # Ensure content is never None
                })
            
            elif isinstance(msg, SystemMessage):
                llm_messages.append({
                    "role": "system",
                    "content": msg.content or ""  # Ensure content is never None
                })
            
            elif isinstance(msg, EnvironmentMessage):
                # Environment events as user context
                llm_messages.append({
                    "role": "user",
                    "content": f"[Environment Event: {msg.event_type}] {msg.content}"
                })
            
            elif isinstance(msg, LLMThinkMessage):
                llm_messages.append({
                    "role": "assistant",
                    "content": msg.content or ""  # Ensure content is never None
                })
            
            elif isinstance(msg, LLMRespondMessage):
                llm_messages.append({
                    "role": "assistant",
                    "content": msg.content or ""  # Ensure content is never None
                })
            
            elif isinstance(msg, ToolCallMessage):
                # Tool calls in OpenAI format
                tool_calls = []
                for tc in msg.tool_calls:
                    tool_calls.append({
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.tool_name,
                            "arguments": str(tc.arguments)  # JSON string
                        }
                    })

                llm_messages.append({
                    "role": "assistant",
                    "content": msg.thought or "",  # OpenAI API requires string, not null
                    "tool_calls": tool_calls
                })
            
            elif isinstance(msg, ToolResultObservation):
                llm_messages.append({
                    "role": "tool",
                    "tool_call_id": msg.call_id,
                    "content": msg.content or ""  # Ensure content is never None
                })
            
            elif isinstance(msg, ErrorObservation):
                # Errors as tool results or user feedback
                llm_messages.append({
                    "role": "user",
                    "content": f"[Error] {msg.content}"
                })

        return llm_messages
    
    def clear(self) -> None:
        """Clear all messages."""
        self.messages = []
    
    def __len__(self) -> int:
        """Return number of messages."""
        return len(self.messages)
