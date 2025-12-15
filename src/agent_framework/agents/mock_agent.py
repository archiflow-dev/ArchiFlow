"""
Mock Agent Implementation.
"""
import logging
import json
from typing import Optional, Callable

from .base import BaseAgent
from ..messages.types import (
    BaseMessage, UserMessage, SystemMessage, ToolCallMessage, 
    LLMRespondMessage, WaitForUserInput,
    StopMessage, ToolCall, AgentFinishedMessage, BatchToolResultObservation, ToolResultObservation
)
from ..llm.provider import LLMResponse

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 5

class MockAgent(BaseAgent):
    """
    Agent specialized for coding tasks.
    Equipped with file operations and a coding-focused system prompt.
    """
    
    def __init__(self, llm, config):
        self.sequence_counter = 0
        self.session_id = "mock_session"
        super().__init__(llm, config)
        
        # Add system message
        sys_msg = SystemMessage(
            session_id=self.session_id,
            sequence=self._next_sequence(),
            content=self.get_system_message()
        )
        self.history.add(sys_msg)

    def get_system_message(self) -> str:
        return """You are an expert software engineer.
You have access to file operations (read, write, list).
Always verify file contents before editing.
Write clean, documented, and tested code.
When asked to implement something, break it down into steps."""

    def _next_sequence(self) -> int:
        self.sequence_counter += 1
        return self.sequence_counter

    def step(self, message: BaseMessage) -> BaseMessage:
        """Process message and execute think-act loop."""
        if self.sequence_counter == MAX_ITERATIONS:
            logger.info(f"calling LLM {self.sequence_counter}")
            return AgentFinishedMessage(
                session_id=self.session_id,
                sequence=self._next_sequence(),
                reason="Mock agent stopped."
            )
        # if the message is a user message, call the LLM and return a tool call message
        if isinstance(message, UserMessage):
            logger.info(f"calling LLM {self.sequence_counter}")
            return ToolCallMessage(
                session_id=self.session_id,
                sequence=self._next_sequence(),
                thought="I need to read the readme.md file.",
                tool_calls=[ToolCall(id="call_1", tool_name="read_file", arguments={"path": "/readme.md"})]
            )
        # if the message is a tool call observation, return a another tool call message for mock
        if isinstance(message, ToolResultObservation):
            logger.info(f"calling LLM {self.sequence_counter}")
            logger.info(f"tool call observation: {message}")
            return ToolCallMessage(
                session_id=self.session_id,
                sequence=self._next_sequence(),
                thought="I need to write the readme.md file.",
                tool_calls=[ToolCall(id="call_1", tool_name="write_file", arguments={"path": "/readme.md"})]
            )
        # if the message is a batch tool call observation, return a another tool call message for mock
        if isinstance(message, BatchToolResultObservation):
            logger.info(f"calling LLM {self.sequence_counter}")
            logger.info(f"batch tool call observation: {message}")
            return ToolCallMessage(
                session_id=self.session_id,
                sequence=self._next_sequence(),
                thought="I need to write the readme.md file.",
                tool_calls=[ToolCall(id="call_1", tool_name="write_file", arguments={"path": "/readme.md", "content": "This is the content of the readme."})]
            )

