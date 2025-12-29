"""
Message format conversion between internal and LLM formats.

This module provides the MessageFormatter class for converting between
internal message types and LLM API formats (OpenAI-compatible).
"""
import json
import logging
from typing import Any, Dict, List, Optional

from ..messages.types import (
    AgentFinishedMessage,
    BaseMessage,
    BatchToolResultObservation,
    EnvironmentMessage,
    LLMRespondMessage,
    ProjectContextMessage,
    SystemMessage,
    ToolCallMessage,
    ToolResultObservation,
    UserMessage,
)

logger = logging.getLogger(__name__)


class MessageFormatter:
    """Converts messages between internal and LLM API formats.

    This class is responsible for formatting messages in the structure
    expected by LLM APIs (OpenAI, Anthropic, etc.).
    """

    def to_llm_format(self, messages: List[BaseMessage]) -> List[Dict[str, Any]]:
        """Convert internal messages to LLM API format.

        Args:
            messages: List of internal BaseMessage objects

        Returns:
            List of dictionaries in LLM API format
        """
        llm_messages = []

        for msg in messages:
            converted = self._convert_message(msg)

            # Handle batch results separately (each becomes its own message)
            if isinstance(msg, BatchToolResultObservation):
                for result in msg.results:
                    llm_messages.append({
                        "role": "tool",
                        "tool_call_id": result.call_id,
                        "content": result.content
                    })
                continue

            if converted:
                llm_messages.append(converted)

        return llm_messages

    def _convert_message(self, msg: BaseMessage) -> Optional[Dict[str, Any]]:
        """Convert a single message to LLM format.

        Args:
            msg: Internal message to convert

        Returns:
            Dictionary in LLM API format, or None if message type unknown
        """
        if isinstance(msg, UserMessage):
            return {
                "role": "user",
                "content": msg.content or ""
            }

        elif isinstance(msg, SystemMessage):
            return {
                "role": "system",
                "content": msg.content or ""
            }

        elif isinstance(msg, LLMRespondMessage):
            return {
                "role": "assistant",
                "content": msg.content or ""
            }

        elif isinstance(msg, ToolCallMessage):
            msg_dict = {"role": "assistant"}

            # Add content if present
            if hasattr(msg, 'content') and msg.content:
                msg_dict["content"] = msg.content

            # Add tool calls
            tool_calls = []
            for tc in msg.tool_calls:
                tool_calls.append({
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.tool_name,
                        "arguments": (
                            json.dumps(tc.arguments)
                            if isinstance(tc.arguments, dict)
                            else str(tc.arguments)
                        )
                    }
                })
            msg_dict["tool_calls"] = tool_calls

            return msg_dict

        elif isinstance(msg, ToolResultObservation):
            return {
                "role": "tool",
                "tool_call_id": msg.call_id,
                "content": msg.content or ""
            }

        elif isinstance(msg, EnvironmentMessage):
            return {
                "role": "user",
                "content": f"[Environment: {msg.event_type}] {msg.content}"
            }

        elif isinstance(msg, ProjectContextMessage):
            return {
                "role": "system",
                "content": msg.context or ""
            }

        elif isinstance(msg, AgentFinishedMessage):
            return {
                "role": "assistant",
                "content": f"[Task completed: {msg.reason}]"
            }

        elif isinstance(msg, BatchToolResultObservation):
            # Handled separately in to_llm_format()
            return None

        else:
            logger.warning(f"Unknown message type: {type(msg).__name__}")
            return None

    def from_llm_format(self, llm_messages: List[Dict[str, Any]]) -> List[BaseMessage]:
        """Convert LLM API format to internal messages.

        Args:
            llm_messages: List of dictionaries in LLM API format

        Returns:
            List of internal BaseMessage objects

        Note:
            This is a placeholder for future implementation.
            Currently not needed as we only convert TO LLM format.
        """
        raise NotImplementedError(
            "Conversion from LLM format to internal format is not yet implemented"
        )
