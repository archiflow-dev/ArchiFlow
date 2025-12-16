"""
Base Agent Implementation.

Simplified base class and a concrete SimpleAgent.
"""
from typing import Optional, Callable, List, Dict, Any
from abc import ABC, abstractmethod
import logging
import json

from ..messages.types import (
    BaseMessage, UserMessage, SystemMessage, ToolCallMessage,
    ToolResultObservation, ErrorObservation, LLMRespondMessage,
    StopMessage, ToolCall
)
from ..memory.history import HistoryManager
from ..memory.summarizer import LLMSummarizer
from ..memory.tracker import EnvironmentTracker
from ..memory.persistence import PersistentMemory
from ..memory.context import ContextInjector
from ..llm.provider import LLMProvider, LLMResponse
from ..tools.tool_base import ToolRegistry
from ..config.manager import AgentConfig

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract base agent with integrated memory system.
    """

    def __init__(self, llm: LLMProvider, config: AgentConfig, tools: Optional[ToolRegistry] = None):
        """
        Initialize the agent.

        Args:
            llm: LLM provider
            config: Agent configuration
            tools: Optional tool registry (for token counting)
        """
        self.llm = llm
        self.config = config

        # Get session_id from config (handle both dict and Pydantic model)
        if isinstance(config, dict):
            session_id = config.get("session_id", "default")
        else:
            session_id = getattr(config, "session_id", "default")

        # Count tokens in system prompt
        system_prompt = self.get_system_message()
        system_prompt_tokens = llm.count_tokens([
            {"role": "system", "content": system_prompt}
        ])

        # Count tokens in tools (if available)
        tools_tokens = 0
        if tools is not None:
            tools_schema = tools.to_llm_schema()
            tools_tokens = llm.count_tools_tokens(tools_schema)

        # Get retention window from config
        retention_window = 20  # Default
        if isinstance(config, dict):
            retention_window = config.get("retention_window", 20)
        else:
            retention_window = getattr(config, "retention_window", 20)

        # Initialize Memory Components with model-aware limits
        self.history = HistoryManager(
            summarizer=LLMSummarizer(llm),
            model_config=llm.model_config,
            system_prompt_tokens=system_prompt_tokens,
            tools_tokens=tools_tokens,
            retention_window=retention_window
        )
        self.tracker = EnvironmentTracker()
        self.persistent_memory = PersistentMemory()

        self.context_injector = ContextInjector(
            tracker=self.tracker,
            memory=self.persistent_memory,
            session_id=session_id
        )

        logger.info(
            f"BaseAgent initialized: model={llm.model}, "
            f"system_tokens={system_prompt_tokens}, tools_tokens={tools_tokens}, "
            f"history_max_tokens={self.history.max_tokens}"
        )

    @abstractmethod
    def get_system_message(self) -> str:
        """Get the system message for this agent."""
        pass

    @abstractmethod
    def step(self, message: BaseMessage) -> BaseMessage:
        """Process a single message."""
        pass
        
    def _update_memory(self, message: BaseMessage) -> None:
        """Update memory components based on the message."""
        self.history.add(message)
        
        # Update tracker if it's a tool result
        if isinstance(message, ToolResultObservation):
            # We need the tool name and args to update the tracker properly.
            # Ideally, ToolResultObservation should contain this info or we look it up.
            # For now, we might need to rely on the previous ToolCallMessage in history.
            # This is a limitation of the current message structure.
            # Let's try to find the matching tool call in history.
            for msg in reversed(self.history.get_messages()):
                if isinstance(msg, ToolCallMessage):
                    for tc in msg.tool_calls:
                        if tc.id == message.call_id:
                            self.tracker.update(tc.tool_name, tc.arguments, message.content)
                            return


class SimpleAgent(BaseAgent):
    """
    Concrete implementation of a simple agent.
    """

    def __init__(
        self,
        session_id: str,
        llm: LLMProvider,
        tools: Optional[ToolRegistry] = None,
        system_prompt: str = "You are a helpful assistant.",
        publish_callback: Optional[Callable[[BaseMessage], None]] = None
    ):
        # Set system_prompt BEFORE calling super().__init__ since BaseAgent init calls get_system_message()
        self.session_id = session_id
        self.tools = tools or ToolRegistry()
        self.tool_registry = self.tools

        # Add instructions about finish_task and handling failures
        if system_prompt == "You are a helpful assistant.":
            # Default prompt - add important instructions
            self.system_prompt = """You are a helpful assistant with access to various tools.

IMPORTANT: When you have completed the user's request, you MUST call the finish_task tool
with the reason for completion. This signals that you are done and the task is complete.

If a tool fails or returns insufficient information:
1. Do your best with what you have or with your general knowledge
2. Explain the limitations to the user
3. Then call finish_task

Don't keep trying the same tool repeatedly if it's clearly not working."""
        else:
            # Custom prompt - use as is (user might have their own finish_task instructions)
            self.system_prompt = system_prompt

        self.publish_callback = publish_callback
        self.sequence_counter = 0
        self.is_running = True
        self._system_added = False

        # Use dict config for flexibility
        config = {
            "name": "SimpleAgent",
            "version": "1.0.0",
            "session_id": session_id
        }
        super().__init__(llm, config)

        # Always add system message (it now includes finish_task instructions)
        # The enhanced prompt is used even for the default case
        self.history.add(SystemMessage(
            session_id=self.session_id,
            sequence=self._next_sequence(),
            content=self.system_prompt
        ))
        self._system_added = True

    def get_system_message(self) -> str:
        """Get the system message for this agent."""
        from datetime import datetime

        # Get current date
        current_date = datetime.now().strftime("%Y-%m-%d")
        current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Build system message with date context
        message_parts = [self.system_prompt]
        message_parts.append(f"\n\nCurrent Date: {current_date}")
        message_parts.append(f"Current DateTime: {current_datetime}")

        return "".join(message_parts)
        
    def get_name(self) -> str:
        if isinstance(self.config, dict):
            return self.config.get("name", "SimpleAgent")
        return self.config.name
        
    def get_description(self) -> str:
        return "A simple agent for testing."

    def _next_sequence(self) -> int:
        seq = self.sequence_counter
        self.sequence_counter += 1
        return seq

    def step(self, message: BaseMessage) -> BaseMessage:
        """Process a message."""
        if not self.is_running:
            return None
            
        # 1. Update Memory
        self._update_memory(message)
        
        # 2. Handle Stop
        if isinstance(message, StopMessage):
            self.is_running = False
            return None
            
        # 3. Generate Context
        # In a real agent, we'd inject this. For SimpleAgent, we might skip or just append.
        # context_msg = self.context_injector.generate_context_message(self._next_sequence())
        # self.history.add(context_msg)
            
        # 4. Call LLM
        # Convert history to LLM format
        messages = self.history.to_llm_format()
        
        # Get tools schema
        tools_schema = self.tools.to_llm_schema() if self.tools else None
        
        # Call LLM
        response = self.llm.generate(messages, tools=tools_schema)
        
        # 5. Process Response
        # Handle tool calls
        if response.tool_calls:
            # Create ToolCallMessage
            tool_calls = []
            for tc in response.tool_calls:
                tool_calls.append(ToolCall(
                    id=tc.id,
                    tool_name=tc.name,
                    arguments=json.loads(tc.arguments) if isinstance(tc.arguments, str) else tc.arguments
                ))
                
            tool_msg = ToolCallMessage(
                session_id=self.session_id,
                sequence=self._next_sequence(),
                tool_calls=tool_calls,
                thought=response.content
            )
            
            # Update history and publish tool call
            self._update_memory(tool_msg)
            if self.publish_callback:
                self.publish_callback(tool_msg)
        
        # Handle content (might also have tool calls)
        if response.content and not response.tool_calls:
            # Only create LLMRespondMessage if there are no tool calls
            # (if there are tool calls, content is included in ToolCallMessage.thought)
            content_msg = LLMRespondMessage(
                session_id=self.session_id,
                sequence=self._next_sequence(),
                content=response.content
            )
            
            # Update history and publish
            self._update_memory(content_msg)
            if self.publish_callback:
                self.publish_callback(content_msg)
                
            return content_msg
        elif response.content and response.tool_calls:
            # Both content and tool calls - publish content as separate message
            content_msg = LLMRespondMessage(
                session_id=self.session_id,
                sequence=self._next_sequence(),
                content=response.content
            )
            
            # Update history and publish
            self._update_memory(content_msg)
            if self.publish_callback:
                self.publish_callback(content_msg)
        
        # Return the last message
        if response.tool_calls:
            return tool_msg if 'tool_msg' in locals() else None
        return None
