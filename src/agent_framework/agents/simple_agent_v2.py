"""
Enhanced SimpleAgent with tool support and profiles.

This module provides a refactored SimpleAgent that can perform general tasks
using tools, similar to CodingAgent but with a broader focus.
"""

from typing import Optional, Callable, Dict, List, Any, Set
import logging
import json
from datetime import datetime

from .base import BaseAgent
from .profiles import AgentProfile, get_profile, get_tools_for_profile, SYSTEM_PROMPTS
from ..messages.types import (
    BaseMessage, UserMessage, SystemMessage, ToolCallMessage,
    ToolResultObservation, ErrorObservation, LLMRespondMessage,
    StopMessage, ToolCall
)
from ..memory.history import HistoryManager
from ..tools.tool_base import ToolRegistry
from ..tools.core import load_tools_by_category
from ..llm.provider import LLMProvider

logger = logging.getLogger(__name__)


class SimpleAgent(BaseAgent):
    """
    Enhanced SimpleAgent with tool support and configurable profiles.

    This agent can perform various tasks using tools, with its behavior
    and capabilities defined by its profile configuration.
    """

    def __init__(
        self,
        session_id: str,
        llm: LLMProvider,
        profile: str = "general",
        custom_prompt: Optional[str] = None,
        tools: Optional[ToolRegistry] = None,
        publish_callback: Optional[Callable[[BaseMessage], None]] = None,
        config: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        """
        Initialize the enhanced SimpleAgent.

        Args:
            session_id: Unique identifier for the session
            llm: LLM provider for generating responses
            profile: Agent profile name (e.g., "general", "analyst", "researcher")
            custom_prompt: Optional custom system prompt (overrides profile prompt)
            tools: Optional tool registry (auto-loaded from profile if not provided)
            publish_callback: Optional callback for publishing messages
            config: Additional configuration options
            **kwargs: Additional arguments
        """
        # Load profile configuration
        self.profile_name = profile
        self.profile = get_profile(profile) if profile != "custom" else None

        # Set system prompt
        if custom_prompt:
            self.system_prompt = custom_prompt
        elif self.profile:
            self.system_prompt = self.profile.system_prompt
        else:
            self.system_prompt = SYSTEM_PROMPTS["general"]

        # Initialize session and state
        self.session_id = session_id
        self.publish_callback = publish_callback
        self.sequence_counter = 0
        self.is_running = True
        self._system_added = False

        # Initialize tools
        if tools:
            self.tools = tools
        else:
            # Load tools based on profile
            self.tools = self._load_tools_for_profile(profile)

        self.tool_registry = self.tools

        # Store configuration
        self.agent_config = config or {}
        self.settings = self._merge_settings(**kwargs)

        # Prepare config for BaseAgent
        base_config = {
            "name": f"SimpleAgent-{profile}",
            "version": "2.0.0",
            "session_id": session_id,
            "profile": profile,
            "capabilities": self.profile.capabilities if self.profile else [],
            **self.agent_config
        }

        # Initialize base agent (this will call get_system_message())
        super().__init__(llm, base_config, self.tools)

        # Add system message to history
        self.history.add(SystemMessage(
            session_id=self.session_id,
            sequence=self._next_sequence(),
            content=self.system_prompt
        ))
        self._system_added = True

        logger.info(
            f"Enhanced SimpleAgent initialized: profile={profile}, "
            f"tools={len(self.tools.list_tools())}, "
            f"capabilities={self.settings.get('capabilities', [])}"
        )

    def _load_tools_for_profile(self, profile: str) -> ToolRegistry:
        """Load tools based on the agent profile."""
        tool_registry = ToolRegistry()

        if profile == "custom":
            # For custom profile, load basic tools + finish_task
            tool_categories = ["file", "web", "task"]
        else:
            # Get tool categories from profile
            profile_config = get_profile(profile)
            tool_categories = profile_config.tool_categories
            # Always include finish_task tool
            if "task" not in tool_categories:
                tool_categories.append("task")

        # Load tools by category
        for category in tool_categories:
            try:
                category_tools = load_tools_by_category(category)
                for tool in category_tools:
                    tool_registry.register(tool)
            except Exception as e:
                logger.warning(f"Failed to load tools for category '{category}': {e}")

        return tool_registry

    def _merge_settings(self, **kwargs) -> Dict[str, Any]:
        """Merge profile settings with provided kwargs."""
        settings = {}

        # Start with profile defaults
        if self.profile:
            settings.update(self.profile.default_settings)

        # Override with provided kwargs
        settings.update(kwargs)

        # Add capabilities from profile
        if self.profile:
            settings['capabilities'] = self.profile.capabilities

        return settings

    def get_system_message(self) -> str:
        """Get the system message for this agent."""
        from datetime import datetime

        # Get current date
        current_date = datetime.now().strftime("%Y-%m-%d")
        current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Build system message with date context
        message_parts = [self.system_prompt]

        # Add date context
        message_parts.append(f"\n\nCurrent Date: {current_date}")
        message_parts.append(f"Current DateTime: {current_datetime}")

        # Include information about available tools in the system prompt
        tool_info = self._get_tool_info()
        if tool_info:
            message_parts.append(f"\n\nAvailable tools:\n{tool_info}")

        return "".join(message_parts)

    def _get_tool_info(self) -> str:
        """Get information about available tools."""
        if not self.tools or not self.tools.list_tools():
            return ""

        tool_descriptions = []
        for tool in self.tools.list_tools():
            tool_name = tool.name if hasattr(tool, 'name') else str(tool)
            if tool and hasattr(tool, 'description'):
                tool_descriptions.append(f"- {tool_name}: {tool.description}")

        return "\n".join(tool_descriptions)

    def switch_profile(self, new_profile: str, custom_prompt: Optional[str] = None) -> None:
        """
        Dynamically switch the agent's profile.

        Args:
            new_profile: New profile name
            custom_prompt: Optional custom prompt for the new profile
        """
        logger.info(f"Switching SimpleAgent profile from {self.profile_name} to {new_profile}")

        # Update profile
        self.profile_name = new_profile
        self.profile = get_profile(new_profile) if new_profile != "custom" else None

        # Update system prompt
        if custom_prompt:
            self.system_prompt = custom_prompt
        elif self.profile:
            self.system_prompt = self.profile.system_prompt

        # Reload tools
        self.tools = self._load_tools_for_profile(new_profile)
        self.tool_registry = self.tools

        # Update settings
        self.settings = self._merge_settings()

        # Update system message in history
        self._update_system_message()

        logger.info(f"Profile switched: {new_profile}, tools: {len(self.tools.list_tools())}")

    def _update_system_message(self) -> None:
        """Update the system message in the conversation history."""
        # Find and update the system message
        for i, msg in enumerate(self.history.get_messages()):
            if isinstance(msg, SystemMessage):
                msg.content = self.get_system_message()
                return

        # If not found, add it
        self.history.add(SystemMessage(
            session_id=self.session_id,
            sequence=self._next_sequence(),
            content=self.get_system_message()
        ))

    def add_tool(self, tool) -> None:
        """Add a new tool to the agent's registry."""
        self.tools.register(tool)
        logger.info(f"Added tool: {tool.name}")

    def remove_tool(self, tool_name: str) -> None:
        """Remove a tool from the agent's registry."""
        if self.tools.get(tool_name) is not None:
            del self.tools.tools[tool_name]
            logger.info(f"Removed tool: {tool_name}")

    def get_capabilities(self) -> List[str]:
        """Get the agent's current capabilities."""
        return self.settings.get('capabilities', [])

    def get_profile_info(self) -> Dict[str, Any]:
        """Get information about the current profile."""
        return {
            "name": self.profile_name,
            "description": self.profile.description if self.profile else "Custom profile",
            "capabilities": self.get_capabilities(),
            "tools": [tool.name for tool in self.tools.list_tools()],
            "settings": self.settings
        }

    def _next_sequence(self) -> int:
        """Get the next sequence number for messages."""
        seq = self.sequence_counter
        self.sequence_counter += 1
        return seq

    def step(self, message: BaseMessage) -> BaseMessage:
        """
        Process a single message using the enhanced agent capabilities.

        This extends the original step method to better handle tool usage
        and provide more sophisticated response generation.
        """
        if not self.is_running:
            return None

        # 1. Update Memory
        self._update_memory(message)

        # 2. Handle Stop
        if isinstance(message, StopMessage):
            self.is_running = False
            return None

        # 3. Process User Message
        if isinstance(message, UserMessage):
            # Generate response using LLM
            return self._generate_response(message)

        # 4. Handle Tool Results
        elif isinstance(message, ToolResultObservation):
            # Update tracker and generate follow-up
            self._update_tracker_from_tool_result(message)
            return self._generate_followup_response()

        # 5. Handle Other Message Types
        else:
            logger.warning(f"Unexpected message type in step(): {type(message)}")
            return None

    def _generate_response(self, user_message: UserMessage) -> BaseMessage:
        """Generate a response to a user message."""
        # Prepare context from history
        messages = self.history.to_llm_format()

        # Get tools schema
        tools_schema = self.tools.to_llm_schema() if self.tools else None

        # Generate LLM response
        response = self.llm.generate(messages, tools=tools_schema)

        # Process response
        return self._process_llm_response(response)

    def _process_llm_response(self, llm_response) -> BaseMessage:
        """Process the LLM response and handle tool calls."""
        messages_created = []

        # Handle tool calls
        if llm_response.tool_calls:
            tool_calls = []
            for tc in llm_response.tool_calls:
                tool_calls.append(ToolCall(
                    id=tc.id,
                    tool_name=tc.name,
                    arguments=json.loads(tc.arguments) if isinstance(tc.arguments, str) else tc.arguments
                ))

            # Create tool call message
            tool_msg = ToolCallMessage(
                session_id=self.session_id,
                sequence=self._next_sequence(),
                tool_calls=tool_calls,
                thought=llm_response.content
            )

            # Update history and publish
            self._update_memory(tool_msg)
            if self.publish_callback:
                self.publish_callback(tool_msg)

            messages_created.append(tool_msg)

        # Handle content response
        if llm_response.content:
            # If there were tool calls, include content as thought
            if llm_response.tool_calls:
                # Content already included in tool_msg.thought
                pass
            else:
                # Create separate content message
                content_msg = LLMRespondMessage(
                    session_id=self.session_id,
                    sequence=self._next_sequence(),
                    content=llm_response.content
                )

                # Update history and publish
                self._update_memory(content_msg)
                if self.publish_callback:
                    self.publish_callback(content_msg)

                messages_created.append(content_msg)

        # Return the last message created
        return messages_created[-1] if messages_created else None

    def _generate_followup_response(self) -> Optional[BaseMessage]:
        """Generate a follow-up response after tool execution."""
        # Get updated conversation history
        messages = self.history.to_llm_format()

        # Generate follow-up without additional tools
        response = self.llm.generate(messages, tools=None)

        if response.content:
            followup_msg = LLMRespondMessage(
                session_id=self.session_id,
                sequence=self._next_sequence(),
                content=response.content
            )

            # Update history and publish
            self._update_memory(followup_msg)
            if self.publish_callback:
                self.publish_callback(followup_msg)

            return followup_msg

        return None

    def _update_tracker_from_tool_result(self, message: ToolResultObservation) -> None:
        """Update the environment tracker with tool result information."""
        # Find the corresponding tool call in history
        for msg in reversed(self.history.get_messages()):
            if isinstance(msg, ToolCallMessage):
                for tc in msg.tool_calls:
                    if tc.id == message.call_id:
                        self.tracker.update(tc.tool_name, tc.arguments, message.content)
                        return

    def get_name(self) -> str:
        """Get the agent's name."""
        if isinstance(self.config, dict):
            return self.config.get("name", f"SimpleAgent-{self.profile_name}")
        return getattr(self.config, 'name', f"SimpleAgent-{self.profile_name}")

    def get_description(self) -> str:
        """Get the agent's description."""
        if self.profile:
            return self.profile.description
        return "A versatile AI assistant with tool capabilities."