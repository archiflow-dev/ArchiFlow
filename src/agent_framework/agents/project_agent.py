"""
Project Agent Base Class.

Provides common functionality for agents that operate on project directories.
This abstract base class eliminates code duplication between CodingAgent and
CodebaseAnalyzerAgent by centralizing shared logic.
"""
import logging
import json
from pathlib import Path
from typing import Optional, Callable, List, Dict, Any
from abc import abstractmethod

from ..messages.types import (
    BaseMessage, SystemMessage, ToolCallMessage,
    ToolResultObservation, LLMRespondMessage, AgentFinishedMessage,
    ToolCall
)
from ..tools.tool_base import ToolRegistry
from ..llm.provider import LLMProvider
from .base import BaseAgent
from ..runtime.context import ExecutionContext

logger = logging.getLogger(__name__)


class ProjectAgent(BaseAgent):
    """
    Abstract base class for agents that operate on project directories.

    ProjectAgent provides common functionality for project-based agents:
    - Project directory management and validation
    - Execution context creation and management
    - Session ID and sequence counter management
    - Publish callback handling
    - Debug logging infrastructure
    - Standard message processing workflow
    - Tool call processing and formatting
    - finish_task detection and handling
    - Text response handling

    Subclasses must implement:
    - get_system_message() - System prompt (from BaseAgent)
    - _setup_tools() - Tool registry initialization
    - _get_tools_schema() - Tool schema for LLM (allows filtering)

    Subclasses can optionally override:
    - _format_finish_message() - Customize finish message format
    - step() - Add custom message processing logic

    Example:
        class MyAgent(ProjectAgent):
            SYSTEM_PROMPT = '''
            You are MyAgent. Your project directory is: {project_directory}
            '''

            def get_system_message(self) -> str:
                return self.SYSTEM_PROMPT

            def _setup_tools(self):
                # Load and validate tools
                for tool in get_tool_collection().tools:
                    self.tools.register(tool)

            def _get_tools_schema(self) -> List[Dict[str, Any]]:
                # Return all tools (or filter as needed)
                return self.tools.to_llm_schema()
    """

    def __init__(
        self,
        session_id: str,
        llm: LLMProvider,
        project_directory: Optional[str] = None,
        tools: Optional[ToolRegistry] = None,
        publish_callback: Optional[Callable[[BaseMessage], None]] = None,
        debug_log_path: Optional[str] = None,
        agent_name: str = "ProjectAgent",
        agent_version: str = "1.0.0",
        **kwargs
    ):
        """
        Initialize a project-based agent.

        Args:
            session_id: Unique identifier for this session
            llm: LLM provider instance
            project_directory: Root directory for project (defaults to current directory)
            tools: Optional custom tool registry (uses global if None)
            publish_callback: Optional callback for publishing messages to broker
            debug_log_path: Optional path to debug log file for LLM interactions
            agent_name: Name of the agent (for config)
            agent_version: Version of the agent (for config)
            **kwargs: Additional agent-specific parameters (stored but not used by base)

        Raises:
            ValueError: If project_directory does not exist or is not a directory
        """
        # Store agent-specific parameters
        self.session_id = session_id
        self.publish_callback = publish_callback
        self.sequence_counter = 0
        self.is_running = True
        self.debug_log_path = debug_log_path

        # Store additional kwargs for subclass access
        self._kwargs = kwargs

        # Initialize and validate project directory
        self.project_directory = self._validate_project_directory(project_directory)

        # Create execution context
        self.execution_context = self._create_execution_context(session_id)

        logger.info(
            f"{agent_name} initialized with project directory: {self.project_directory}"
        )

        # Initialize tools (delegate to subclass)
        self.tools = tools or ToolRegistry()
        self.tool_registry = self.tools
        self._setup_tools()

        # Call parent constructor
        config = {
            "name": agent_name,
            "version": agent_version,
            "session_id": session_id
        }
        super().__init__(llm, config, tools=self.tools)

        # Store system prompt template (don't add to history)
        # System message will be formatted dynamically on each step
        self._system_prompt_template = self.get_system_message()

    def _validate_project_directory(self, project_directory: Optional[str]) -> Path:
        """
        Validate and resolve project directory path.

        Args:
            project_directory: Path to project directory (None = current directory)

        Returns:
            Resolved absolute path to project directory

        Raises:
            ValueError: If directory does not exist or is not a directory
        """
        if project_directory:
            proj_dir = Path(project_directory).resolve()
        else:
            proj_dir = Path.cwd()

        if not proj_dir.exists():
            raise ValueError(
                f"Project directory does not exist: {proj_dir}"
            )
        if not proj_dir.is_dir():
            raise ValueError(
                f"Project directory is not a directory: {proj_dir}"
            )

        return proj_dir

    def _create_execution_context(self, session_id: str) -> ExecutionContext:
        """
        Create execution context with working directory.

        Args:
            session_id: Session identifier

        Returns:
            ExecutionContext configured with project directory
        """
        return ExecutionContext(
            session_id=session_id,
            working_directory=str(self.project_directory)
        )

    def _format_system_prompt(self) -> str:
        """
        Format system prompt with current dynamic state.

        Formats the system prompt template with current project_directory
        and other dynamic context. This is called on each step() to ensure
        the LLM always sees current state.

        Subclasses can override to inject additional dynamic context:
            def _format_system_prompt(self):
                git_info = self._get_git_info()
                return self._system_prompt_template.format(
                    project_directory=str(self.project_directory),
                    git_branch=git_info['branch'],
                    git_uncommitted=git_info['uncommitted_count']
                )

        Returns:
            Formatted system prompt string with current state
        """
        return self._system_prompt_template.format(
            project_directory=str(self.project_directory)
        )

    @abstractmethod
    def _setup_tools(self):
        """
        Setup tool registry for this agent.

        Subclasses must implement this to:
        1. Register required tools in self.tools
        2. Validate tools are available
        3. Set execution context on tools if needed

        Example:
            def _setup_tools(self):
                # Load all tools
                for tool in get_tool_collection().tools:
                    self.tools.register(tool)

                # Validate required tools
                required = ["edit", "read", "bash"]
                for tool_name in required:
                    if not self.tools.get(tool_name):
                        raise ValueError(f"Missing required tool: {tool_name}")
        """
        pass

    @abstractmethod
    def _get_tools_schema(self) -> List[Dict[str, Any]]:
        """
        Get tool schema for LLM.

        Allows subclasses to filter which tools are exposed to the LLM.
        This is critical for agents like CodebaseAnalyzerAgent that should
        only use read-only tools.

        Returns:
            List of tool schemas in OpenAI format

        Example:
            def _get_tools_schema(self):
                # Expose all tools
                return self.tools.to_llm_schema()

            def _get_tools_schema(self):
                # Filter to specific tools
                allowed = ["glob", "grep", "read"]
                return self.tools.to_llm_schema(tool_names=allowed)
        """
        pass

    def _next_sequence(self) -> int:
        """
        Get next sequence number for messages.

        Returns:
            Next sequence number (auto-increments)
        """
        seq = self.sequence_counter
        self.sequence_counter += 1
        return seq

    def _log_debug_info(
        self,
        messages: List[Dict[str, Any]],
        tools_schema: List[Dict[str, Any]],
        response: Any
    ):
        """
        Log debug information about LLM interactions to file.

        Only logs if debug_log_path is set.

        Args:
            messages: Messages sent to LLM
            tools_schema: Tool schema sent to LLM
            response: Response from LLM
        """
        if not self.debug_log_path:
            return

        try:
            # Prepare log entry
            log_entry = {
                "step": self.sequence_counter,
                "timestamp": __import__('datetime').datetime.now().isoformat(),
                "session_id": self.session_id,
                "messages": messages,
                "response": {
                    "content": getattr(response, 'content', None),
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "name": tc.name,
                            "arguments": tc.arguments
                        } for tc in response.tool_calls
                    ] if hasattr(response, 'tool_calls') and response.tool_calls else [],
                    "stop_reason": getattr(response, 'stop_reason', None),
                    "usage": getattr(response, 'usage', None)
                }
            }

            # Ensure directory exists
            log_path = Path(self.debug_log_path)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            # Append to log file
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry, indent=2, ensure_ascii=False))
                f.write('\n' + '='*80 + '\n')

            logger.debug(f"Debug info logged to {self.debug_log_path}")

        except Exception as e:
            logger.error(f"Failed to write debug log: {e}")

    def _handle_finish_task(
        self,
        tool_calls: List[Any]
    ) -> Optional[AgentFinishedMessage]:
        """
        Check for finish_task tool call and create AgentFinishedMessage.

        Searches tool_calls for finish_task. If found:
        - Extracts reason and result from arguments
        - Formats finish message via _format_finish_message()
        - Creates AgentFinishedMessage
        - Sets is_running = False
        - Updates memory and publishes

        Args:
            tool_calls: List of tool calls from LLM response

        Returns:
            AgentFinishedMessage if finish_task found, None otherwise
        """
        for tc in tool_calls:
            if tc.name == "finish_task":
                # Extract arguments
                args = tc.arguments
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except:
                        args = {}

                reason = args.get("reason", "Task completed")
                result = args.get("result", "")

                # Format finish message (subclass can override)
                finish_reason = self._format_finish_message(reason, result)

                # Create finished message
                finished_msg = AgentFinishedMessage(
                    session_id=self.session_id,
                    sequence=self._next_sequence(),
                    reason=finish_reason
                )

                # Stop agent
                self.is_running = False
                self._update_memory(finished_msg)

                # Publish
                if self.publish_callback:
                    self.publish_callback(finished_msg)

                return finished_msg

        return None

    def _format_finish_message(self, reason: str, result: str) -> str:
        """
        Format the finish message content.

        Subclasses can override to customize format:
        - CodingAgent: Uses default (reason only)
        - CodebaseAnalyzerAgent: Overrides to include report

        Args:
            reason: Reason for finishing
            result: Result data (e.g., report for analyzer)

        Returns:
            Formatted finish message string

        Example override:
            def _format_finish_message(self, reason, result):
                return f"{reason}\\n\\n{result}"  # Include result
        """
        return reason  # Default: just reason

    def _process_tool_calls(
        self,
        response: Any
    ) -> Optional[BaseMessage]:
        """
        Process tool calls from LLM response.

        Handles two cases:
        1. finish_task: Stops agent and returns AgentFinishedMessage
        2. Standard tools: Creates ToolCallMessage

        Args:
            response: LLM response object

        Returns:
            ToolCallMessage, AgentFinishedMessage, or None
        """
        if not response.tool_calls:
            return None

        # Check for finish_task first
        finished_msg = self._handle_finish_task(response.tool_calls)
        if finished_msg:
            return finished_msg

        # Standard tool calls
        tool_calls = []
        for tc in response.tool_calls:
            tool_calls.append(ToolCall(
                id=tc.id,
                tool_name=tc.name,
                arguments=json.loads(tc.arguments) if isinstance(tc.arguments, str) else tc.arguments
            ))
        logger.info(f"Content: {response.content}")
        tool_msg = ToolCallMessage(
            session_id=self.session_id,
            sequence=self._next_sequence(),
            tool_calls=tool_calls,
            thought=response.content
        )

        self._update_memory(tool_msg)
        if self.publish_callback:
            self.publish_callback(tool_msg)

        return tool_msg

    def _process_text_response(self, response: Any) -> Optional[LLMRespondMessage]:
        """
        Process text-only response from LLM.

        Creates LLMRespondMessage for responses without tool calls.

        Args:
            response: LLM response object

        Returns:
            LLMRespondMessage or None if no content
        """
        if not response.content:
            return None

        content_msg = LLMRespondMessage(
            session_id=self.session_id,
            sequence=self._next_sequence(),
            content=response.content
        )

        self._update_memory(content_msg)
        if self.publish_callback:
            self.publish_callback(content_msg)

        return content_msg

    def step(self, message: BaseMessage) -> Optional[BaseMessage]:
        """
        Process a message and determine the next action.

        Standard workflow:
        1. Check if agent is running
        2. Update memory with incoming message
        3. Call LLM with history and tools
        4. Process response (tool calls or text)
        5. Log debug info if enabled

        Subclasses can override to add custom behavior, but should
        typically call super().step(message) to preserve core logic.

        Args:
            message: Incoming message (UserMessage or ToolResultObservation)

        Returns:
            Response message (ToolCallMessage, LLMRespondMessage,
            AgentFinishedMessage, or None)

        Example override:
            def step(self, message):
                # Custom pre-processing
                if isinstance(message, UserMessage):
                    self.user_message_count += 1

                # Call parent for standard processing
                response = super().step(message)

                # Custom post-processing
                if isinstance(response, ToolCallMessage):
                    self.tool_call_count += 1

                return response
        """
        if not self.is_running:
            return None

        # 1. Update Memory
        self._update_memory(message)

        # 2. Build messages for LLM
        # Get conversation history (without system message)
        history_messages = self.history.to_llm_format()

        # Format system prompt with current dynamic state
        system_content = self._format_system_prompt()
        system_msg = {"role": "system", "content": system_content}

        # Prepend system message to history for this call only
        messages = [system_msg] + history_messages

        # Get tool schema
        tools_schema = self._get_tools_schema()

        # 3. Call LLM
        try:
            response = self.llm.generate(messages, tools=tools_schema)

            # Debug logging
            if self.debug_log_path:
                self._log_debug_info(messages, tools_schema, response)

        except Exception as e:
            logger.error(f"LLM Generation failed: {e}")
            logger.error(f"Messages that caused error: {len(messages)} total")
            for i, msg in enumerate(messages):
                logger.error(f"  [{i}] role={msg.get('role')}, content={repr(msg.get('content'))[:100]}")
            return None

        # 4. Process Response

        # Handle tool calls (includes finish_task check)
        if response.tool_calls:
            return self._process_tool_calls(response)

        # Handle text content
        if response.content:
            return self._process_text_response(response)

        return None
