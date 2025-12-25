"""
Prompt Refiner Agent - Interactive conversational agent for prompt refinement.

This agent helps users improve their prompts through multi-turn conversation,
quality analysis, and iterative refinement.
"""
import logging
from typing import Optional, Callable
from datetime import datetime

from .base import BaseAgent, get_environment_context
from ..messages.types import (
    BaseMessage, UserMessage, SystemMessage, ToolCallMessage,
    ToolResultObservation, StopMessage, LLMRespondMessage,
    AgentFinishedMessage, ToolCall
)
from ..llm.provider import LLMProvider
from ..tools.tool_base import ToolRegistry

logger = logging.getLogger(__name__)


class PromptRefinerAgent(BaseAgent):
    """
    Interactive agent for conversational prompt refinement.

    Workflow:
    1. User provides initial prompt (via slash command or direct message)
    2. Agent calls PromptRefinerTool to analyze quality
    3. Agent reads analysis and asks targeted follow-up questions
    4. User responds, agent refines further or finalizes
    5. Agent saves refined prompt to .archiflow/artifacts/refined_prompts/
    6. Agent copies to clipboard and calls finish_task

    Features:
    - Conversational refinement (not form-filling)
    - Quality scoring across 5 dimensions
    - Iterative improvement until quality >= 8.5
    - Artifact storage with full context
    - Clipboard integration for easy use
    """

    # System prompt for the agent
    SYSTEM_PROMPT = """# Prompt Refinement Specialist

You are an expert prompt engineer helping users improve their prompts through natural conversation.

## Your Process

### 1. Initial Analysis

When the user provides a prompt:
- Call the `refine_prompt` tool with their prompt
- Read the quality analysis carefully (scores for clarity, specificity, actionability, completeness, structure)
- Identify specific issues and improvement opportunities

### 2. Conversational Refinement

Based on the analysis:
- Ask 2-3 targeted follow-up questions to address gaps
- Be conversational and natural, not interrogative
- Focus on: missing context, unclear constraints, specificity gaps, actionability issues
- Example: "I noticed you want to build a web app. What specific features are essential for your MVP?"
  (NOT: "List all features and requirements")

### 3. Iterative Improvement

As the user answers:
- Incorporate responses into an improved version
- You can call `refine_prompt` again with the updated version
- Continue until quality_score >= 8.5 OR user is satisfied
- Show before/after comparisons

### 4. Finalization

When refinement is complete:
- Save the final refined prompt to `.archiflow/artifacts/refined_prompts/`
- Use `write` tool with filename format: `{{timestamp}}_{{task_type}}.json`
- Include: metadata, original_prompt, refined_prompt, analysis, conversation_context
- Copy refined prompt to clipboard using `copy_to_clipboard` tool
- Show user a clear before/after summary
- Call `finish_task` with success message

## Important Guidelines

**Be Concise**: Keep questions focused and actionable (2-3 questions max at a time)
**Be Natural**: This is a conversation, not a form to fill out
**Be Helpful**: Explain WHY you're asking each question
**Respect Voice**: Don't over-engineer simple requests - if quality is already 9+, just polish lightly
**Know When to Stop**: Quality >= 8.5 is excellent; >= 9.0 needs minimal or no changes

## Storage Format

When saving artifacts, use this JSON structure:

```json
{{
  "metadata": {{
    "timestamp": "2025-01-24T14:30:22Z",
    "task_type": "<from analysis.detected_task_type>",
    "session_id": "<current session>",
    "quality_score": <final score>,
    "refinement_level": "<from analysis>"
  }},
  "original_prompt": "<user's original>",
  "refined_prompt": "<final improved version>",
  "analysis": {{<full refine_prompt tool output>}},
  "conversation_context": [
    {{"role": "agent", "message": "question 1"}},
    {{"role": "user", "message": "answer 1"}},
    ...
  ],
  "artifacts": {{
    "clipboard_copied": true/false,
    "file_path": ".archiflow/artifacts/refined_prompts/..."
  }}
}}
```

## File Naming

- Directory: `.archiflow/artifacts/refined_prompts/`
- Filename: `{{YYYYMMDD_HHMMSS}}_{{task_type}}.json`
- Task type from `analysis.detected_task_type`, lowercase, underscores for spaces

## Example Flow

User: "Build a web app"
You: *call refine_prompt*
You: "I analyzed your prompt (score: 3.5/10). To help you better, I have a few questions:
      1. What specific features should the web app have?
      2. What technology stack are you most comfortable with?
      3. Who are the target users?"

User: "E-commerce site, React + Node.js, consumers"
You: *incorporate answers*
You: "Great! Let me refine that... *call refine_prompt with updated version*
      Your refined prompt is now at 8.8/10. Here's the result:

      **Original**: Build a web app

      **Refined**: Build an e-commerce web application with:
      - React frontend (with hooks and context API)
      - Node.js/Express backend
      - Product catalog with search/filtering
      - Shopping cart functionality
      - User authentication
      - Payment integration

      Target users: Online consumers

      *saving to artifacts... copying to clipboard... calling finish_task*"

{environment_context}
"""

    def __init__(
        self,
        session_id: str,
        llm: LLMProvider,
        publish_callback: Optional[Callable[[BaseMessage], None]] = None,
        initial_prompt: Optional[str] = None,
    ):
        """
        Initialize the PromptRefinerAgent.

        Args:
            session_id: Unique session identifier
            llm: LLM provider for agent reasoning
            publish_callback: Callback for publishing messages
            initial_prompt: Optional initial prompt to start refinement
        """
        self.session_id = session_id
        self.publish_callback = publish_callback
        self.sequence_counter = 0
        self.is_running = True
        self.initial_prompt = initial_prompt
        self.llm = llm  # Store llm before _setup_tools() needs it

        # Setup tools BEFORE calling super().__init__
        self.tools = ToolRegistry()
        self.tool_registry = self.tools
        self._setup_tools()

        # Call parent with config
        config = {
            "name": "PromptRefinerAgent",
            "version": "1.0.0",
            "session_id": session_id,
            "retention_window": 20  # Keep recent conversation in context
        }
        super().__init__(llm, config, tools=self.tools)

        # Add system message to history
        self.history.add(SystemMessage(
            session_id=self.session_id,
            sequence=self._next_sequence(),
            content=self.get_system_message()
        ))

        logger.info(
            f"PromptRefinerAgent initialized: session={session_id}, "
            f"model={llm.model}, initial_prompt={initial_prompt is not None}"
        )

    def _setup_tools(self):
        """Register required tools for prompt refinement."""
        # Import tools
        from ..tools.prompt_refiner_tool import PromptRefinerTool
        from ..tools.write_tool import WriteTool
        from ..tools.read_tool import ReadTool
        from ..tools.list_tool import ListTool
        from ..tools.finish_tool import FinishAction

        # Register core tools
        self.tools.register(PromptRefinerTool(llm=self.llm))
        self.tools.register(WriteTool())
        self.tools.register(ReadTool())
        self.tools.register(ListTool())
        self.tools.register(FinishAction())

        # Register clipboard tool (optional - graceful degradation)
        try:
            from ..tools.clipboard_tool import ClipboardTool
            self.tools.register(ClipboardTool())
            logger.debug("ClipboardTool registered successfully")
        except ImportError:
            logger.warning("ClipboardTool not available - clipboard copy will be disabled")

        logger.info(f"Registered {len(self.tools.list_tools())} tools for PromptRefinerAgent")

    def get_system_message(self) -> str:
        """Get the system message for this agent."""
        return self.SYSTEM_PROMPT.format(
            environment_context=get_environment_context()
        )

    def _next_sequence(self) -> int:
        """Get next sequence number."""
        self.sequence_counter += 1
        return self.sequence_counter

    def step(self, message: BaseMessage) -> Optional[BaseMessage]:
        """
        Process a single message through the agent.

        Args:
            message: Incoming message (UserMessage, ToolResultObservation, etc.)

        Returns:
            Response message or None if agent stopped
        """
        if not self.is_running:
            return None

        # Handle stop message
        if isinstance(message, StopMessage):
            self.is_running = False
            logger.info(f"PromptRefinerAgent stopped: session={self.session_id}")
            return None

        # Update memory with incoming message
        self._update_memory(message)

        # Get conversation history in LLM format
        history_messages = self.history.to_llm_format()

        # Get tool schemas
        tools_schema = self.tools.to_llm_schema()

        # Call LLM
        try:
            logger.debug(f"Calling LLM with {len(history_messages)} messages and {len(tools_schema)} tools")
            response = self.llm.generate(
                messages=history_messages,
                tools=tools_schema
            )

            # Process response
            if response.tool_calls:
                # Agent wants to use tools
                return self._process_tool_calls(response)
            elif response.content:
                # Agent is responding to user
                return self._process_response(response)
            else:
                logger.warning("LLM returned empty response")
                return None

        except Exception as e:
            logger.error(f"Error in agent step: {e}", exc_info=True)
            # Return error message
            error_msg = LLMRespondMessage(
                session_id=self.session_id,
                sequence=self._next_sequence(),
                content=f"I encountered an error while processing: {str(e)}"
            )
            self._update_memory(error_msg)
            if self.publish_callback:
                self.publish_callback(error_msg)
            return error_msg

    def _process_tool_calls(self, response) -> Optional[BaseMessage]:
        """Process tool calls from LLM response."""
        import json

        # Check for finish_task FIRST - if found, return AgentFinishedMessage directly
        for tc in response.tool_calls:
            if tc.name == "finish_task":
                # Parse arguments
                args = tc.arguments
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except:
                        args = {}

                reason = args.get("reason", "Task completed")

                # Create finished message
                finished_msg = AgentFinishedMessage(
                    session_id=self.session_id,
                    sequence=self._next_sequence(),
                    reason=reason
                )

                # Stop agent
                self.is_running = False
                logger.info(f"PromptRefinerAgent finished: session={self.session_id}")

                # Update memory and publish
                self._update_memory(finished_msg)
                if self.publish_callback:
                    self.publish_callback(finished_msg)

                return finished_msg

        # No finish_task - process standard tool calls
        tool_calls = []
        for tc in response.tool_calls:
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
            thought=response.content if response.content else None
        )

        self._update_memory(tool_msg)

        # Publish to user
        if self.publish_callback:
            self.publish_callback(tool_msg)

        return tool_msg

    def _process_response(self, response) -> Optional[BaseMessage]:
        """Process LLM text response."""
        respond_msg = LLMRespondMessage(
            session_id=self.session_id,
            sequence=self._next_sequence(),
            content=response.content
        )

        self._update_memory(respond_msg)

        # Publish to user
        if self.publish_callback:
            self.publish_callback(respond_msg)

        return respond_msg
