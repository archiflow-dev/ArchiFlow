"""
Base Agent Implementation.

Simplified base class and a concrete SimpleAgent.
"""
import os
from typing import Optional, Callable, List, Dict, Any
from abc import ABC, abstractmethod
import logging
import json
import platform
from datetime import datetime
from pathlib import Path

from ..messages.types import (
    BaseMessage, UserMessage, SystemMessage, ToolCallMessage,
    ToolResultObservation, ErrorObservation, LLMRespondMessage,
    StopMessage, ToolCall, ProjectContextMessage
)
from ..memory.history import HistoryManager
from ..memory.summarizer import LLMSummarizer
from ..memory.tracker import EnvironmentTracker
from ..memory.persistence import PersistentMemory
from ..memory.context import ContextInjector
from ..llm.provider import LLMProvider, LLMResponse
from ..tools.tool_base import ToolRegistry
from ..config.manager import AgentConfig
from ..config.hierarchy import ConfigHierarchy

logger = logging.getLogger(__name__)


def get_environment_context(working_directory: str = None) -> str:
    """
    Get environment context string for agent system prompts.

    Includes:
    - Current date and time
    - Operating system and version
    - Platform architecture
    - Python version
    - Working directory (if provided)

    Args:
        working_directory: Optional working directory to include

    Returns:
        Formatted environment context string
    """
    now = datetime.now()

    # Gather environment info
    env_info = {
        "year": now.strftime("%Y"),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "day_of_week": now.strftime("%A"),
        "os": platform.system(),
        "os_version": platform.version(),
        "architecture": platform.machine(),
        "python_version": platform.python_version(),
    }

    # Build context string
    lines = [
        "## Environment Context",
        f"- Current Year: {env_info['year']}",
        f"- Date: {env_info['date']} ({env_info['day_of_week']})",
        f"- Time: {env_info['time']}",
        f"- OS: {env_info['os']} ({env_info['architecture']})",
        f"- Python: {env_info['python_version']}",
    ]

    if working_directory:
        lines.append(f"- Working Directory: {working_directory}")

    # Add important notes
    lines.append("")
    lines.append(f"IMPORTANT: When searching the web, use {env_info['year']} as the current year (not 2024 or earlier).")

    # Add platform-specific notes
    if env_info['os'] == "Windows":
        lines.append("Note: Use Windows-compatible commands (mkdir, rm, ren, copy, type, dir)")
    elif env_info['os'] in ("Linux", "Darwin"):
        lines.append("Note: Use Unix-compatible commands (mkdir -p, rm, mv, cp, cat, ls)")

    return "\n".join(lines)


class BaseAgent(ABC):
    """
    Abstract base agent with integrated memory system.
    """

    def __init__(
        self,
        llm: LLMProvider,
        config: AgentConfig,
        tools: Optional[ToolRegistry] = None,
        working_dir: Optional[Path] = None,
        include_project_context: bool = False,
    ):
        """
        Initialize the agent.

        Args:
            llm: LLM provider
            config: Agent configuration
            tools: Optional tool registry (for token counting)
            working_dir: Working directory for this agent (for environment context).
                        Defaults to current working directory.
            include_project_context: Whether to load ARCHIFLOW.md context from hierarchy.
        """
        self.llm = llm
        self.config = config
        self.working_dir = working_dir or Path(os.getcwd())
        self.include_project_context = include_project_context

        # Project context support (cached)
        self._config_hierarchy: Optional[ConfigHierarchy] = None
        self._project_context_msg: Optional[ProjectContextMessage] = None
        self._context_injected = False

        # Load project context if enabled
        if include_project_context:
            self._load_project_context()

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

        # Inject project context on first call (if enabled)
        if self.include_project_context and not self._context_injected:
            self._inject_context_if_needed()

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

    def _load_project_context(self) -> None:
        """Load ARCHIFLOW.md context from ConfigHierarchy."""
        if self._config_hierarchy is None:
            self._config_hierarchy = ConfigHierarchy(working_dir=self.working_dir)

        snapshot = self._config_hierarchy.load()

        if snapshot.context:
            # Get session_id from config
            if isinstance(self.config, dict):
                session_id = self.config.get("session_id", "default")
            else:
                session_id = getattr(self.config, "session_id", "default")

            # Use sequence 1 for context (inserted at position 1, after system prompt at sequence 0)
            self._project_context_msg = ProjectContextMessage(
                session_id=session_id,
                sequence=1,
                context=snapshot.context,
                sources=[str(p) for p in snapshot.sources]
            )
            logger.info(
                f"Loaded project context from {len(snapshot.sources)} source(s), "
                f"{len(snapshot.context)} characters"
            )
        else:
            logger.info("No project context found (ARCHIFLOW.md)")

    def reload_project_context(self) -> None:
        """Reload ARCHIFLOW.md context from files."""
        if not self.include_project_context:
            logger.warning("Project context not enabled, call reload_project_context() has no effect")
            return

        if self._config_hierarchy is not None:
            self._config_hierarchy.reload()
            self._load_project_context()
            self._context_injected = False  # Reset injection flag
            logger.info("Project context reloaded")
        else:
            logger.warning("Cannot reload: ConfigHierarchy not initialized")

    def _inject_context_if_needed(self) -> None:
        """
        Inject project context into history if not already injected.

        Handles two agent patterns:
        1. Static system message (in history): SimpleAgent, ResearchAgent, PromptRefinerAgent
           - History: [SystemMessage, UserMessage, ...]
           - Inject context at position 1 (after SystemMessage)
        2. Dynamic system message (prepended at step): ProjectAgent, CodingAgentV3
           - History: [UserMessage, ...] (system message prepended when calling LLM)
           - Inject context at position 0 (so it appears right after prepended system message)

        Final LLM message order should be:
        [SystemMessage, ProjectContextMessage, UserMessage, ...]
        """
        if (self._project_context_msg is not None and
            not self._context_injected and
            not any(isinstance(m, ProjectContextMessage) for m in self.history.get_messages())):

            messages = self.history.get_messages()

            # Detect pattern by checking if SystemMessage is at position 0
            if len(messages) > 0 and isinstance(messages[0], SystemMessage):
                # Static pattern: system message is in history at position 0
                # Insert context at position 1 (right after system message)
                insert_position = 1
                logger.debug("Detected static system message pattern (SystemMessage at position 0)")
            else:
                # Dynamic pattern: system message prepended at step() time
                # Insert context at position 0 (will appear right after prepended system message)
                insert_position = 0
                logger.debug("Detected dynamic system message pattern (no SystemMessage in history)")

            self.history._messages.insert(insert_position, self._project_context_msg)
            self._context_injected = True
            logger.info(
                f"Project context injected at position {insert_position} "
                f"({'after' if insert_position == 1 else 'before'} history messages)"
            )


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
        publish_callback: Optional[Callable[[BaseMessage], None]] = None,
        working_dir: Optional[Path] = None,
        include_project_context: bool = False,
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
        super().__init__(
            llm,
            config,
            working_dir=working_dir,
            include_project_context=include_project_context
        )

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
        # Build system message with environment context
        message_parts = [
            self.system_prompt,
            "",
            get_environment_context(working_directory=str(self.working_dir))
        ]

        return "\n".join(message_parts)
        
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
