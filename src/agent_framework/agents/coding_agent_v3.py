"""
Coding Agent V3 Implementation - Structured, Mode-Based Development Assistant.

This agent follows the successful PPTAgent pattern with distinct modes for different
coding tasks and user approval at each phase.
"""

import logging
import json
import os
import hashlib
from typing import Optional, Callable, Dict, Any, List, Tuple
from pathlib import Path

from ..messages.types import (
    BaseMessage, UserMessage, SystemMessage, ToolCallMessage,
    ToolResultObservation, LLMRespondMessage, ToolCall
)
from ..tools.tool_base import ToolRegistry
from ..llm.provider import LLMProvider
from ..runtime.context import ExecutionContext
from .base import BaseAgent, get_environment_context

logger = logging.getLogger(__name__)


class CodingAgentV3(BaseAgent):
    """
    An advanced coding assistant with structured workflows for different development tasks.

    This agent helps users with:
    - Transforming ideas into specifications
    - Writing production-ready code
    - Debugging and fixing errors
    - Refactoring existing code
    - Adding new features
    - Code review and quality analysis
    - Creating comprehensive tests

    The agent operates in distinct modes based on user needs and existing work:
    - Ideation Mode: Create specifications from ideas
    - Implementation Mode: Write code from specs
    - Debug Mode: Identify and fix errors
    - Refactor Mode: Improve code quality
    - Feature Mode: Add new functionality
    - Review Mode: Analyze code quality
    - Test Mode: Create test suites
    """

    # Core identity (always active)
    CORE_IDENTITY = """You are an expert Software Engineer and Technical Lead. Your role is to:
- Transform ideas into robust, maintainable code
- Write clean, efficient, and well-documented solutions
- Follow best practices and design patterns
- Think about scalability, performance, and security
- Provide thorough testing and error handling

Your session directory is: {session_directory}

You always:
- Write production-ready code
- Include proper documentation
- Consider edge cases and error scenarios
- Follow the language's idiomatic patterns
- Test your code when appropriate"""

    # Mode detection (first priority)
    MODE_DETECTION = """## MODE DETECTION (Always check this first)

Before any other action, assess what the user has provided:

### Step 1: Parse User Input for Intent
Look for specific keywords and patterns:
- Debug/Error: "debug", "fix error", "not working", "broken"
- Refactor: "refactor", "improve", "optimize", "clean up"
- Feature: "add feature", "extend", "new functionality"
- Review: "review", "check", "analyze", "assess"
- Test: "test", "tests", "testing", "coverage"
- Implementation: "implement", "code", "create", "build"

### Step 2: Check Session Directory
Use `list` and `read` to check for existing files:
- specs.md - Requirements and specifications
- implementation_plan.md - Progress tracking
- src/ directory - Existing source code
- tests/ directory - Existing tests
- debug_report.md - Previous debug sessions
- refactor_plan.md - Refactoring strategy

### Step 3: Determine Your Mode

**IF** user provides only an idea AND no files exist:
→ ENTER IDEATION MODE
- Create comprehensive specifications
- Design system architecture
- Plan implementation steps
- Save specs.md for review and approval

**IF** user reports errors OR code is not working:
→ ENTER DEBUG MODE
- Analyze error messages and stack traces
- Identify root cause
- Propose and implement fixes
- Save debug_report.md

**IF** user asks to improve existing code:
→ ENTER REFACTOR MODE
- Analyze code quality and structure
- Identify improvement opportunities
- Plan incremental refactoring
- Save refactor_plan.md

**IF** user wants to add new functionality:
→ ENTER FEATURE MODE
- Analyze existing codebase
- Design feature integration
- Implement new feature
- Update affected code

**IF** user requests code review:
→ ENTER REVIEW MODE
- Comprehensive code analysis
- Check for bugs and issues
- Provide actionable feedback
- Save code_review.md

**IF** user wants or needs tests:
→ ENTER TEST MODE
- Analyze code for test scenarios
- Create comprehensive test suite
- Measure coverage
- Save test_plan.md

**IF** specs exist and ready to implement:
→ ENTER IMPLEMENTATION MODE
- Follow implementation plan
- Generate code file by file
- Show progress at each step

**ALWAYS** announce your mode when starting:
- "I'm entering IDEATION MODE - Creating specifications..."
- "I'm entering DEBUG MODE - Analyzing errors..."
- "I'm entering REFACTOR MODE - Improving code..."
- "I'm entering FEATURE MODE - Adding new functionality..."
- "I'm entering REVIEW MODE - Analyzing code..."
- "I'm entering TEST MODE - Creating tests..."
- "I'm entering IMPLEMENTATION MODE - Writing code..." """

    # Ideation mode workflow
    IDEATION_MODE = """## IDEATION MODE

User provided an idea. Here's your complete workflow:

### Phase 1: Requirements Analysis
1. **Clarify Requirements**
   - Parse user's idea and clarify objectives
   - Identify functional requirements
   - Note non-functional requirements (performance, security, etc.)
   - List assumptions and constraints

2. **System Design**
   - Create high-level architecture
   - Define major components and their responsibilities
   - Choose appropriate technologies and frameworks
   - Design data flow and interfaces

3. **Implementation Planning**
   - Break down into manageable tasks
   - Estimate complexity for each component
   - Plan file structure and organization
   - Identify dependencies and prerequisites

### Phase 2: Save Specifications
1. **MANDATORY: Save specs.md**
   - Complete specification with all requirements
   - Architecture diagram or description
   - Implementation roadmap
   - Technology choices with rationale

2. **Present for Approval**
   - Show requirements summary
   - Explain architecture decisions
   - Present implementation plan
   - Ask: "Does this specification meet your needs? (saved to specs.md)"

3. **⏸️ STOP AND WAIT**
   - Do not proceed without explicit approval

Exit condition: When specs are approved or modified as needed"""

    # Debug mode workflow
    DEBUG_MODE = """## DEBUG MODE

User reported errors or issues. Here's your workflow:

### Phase 1: Error Analysis
1. **Analyze Error Information**
   - Parse error messages and stack traces
   - Identify the type and location of errors
   - Reproduce the issue if possible
   - Gather context about the error

2. **Root Cause Investigation**
   - Trace through code execution
   - Identify the underlying cause
   - Check for related issues
   - Consider edge cases

3. **Solution Design**
   - Propose multiple fix approaches
   - Explain pros and cons of each
   - Recommend the best approach
   - Consider impact on other code

### Phase 2: Fix Implementation
1. **Apply Fix**
   - Implement the chosen solution
   - Make minimal, targeted changes
   - Add comments explaining the fix
   - Test the fix works

2. **Save Debug Report**
   - MANDATORY: Save debug_report.md
   - Document the error analysis
   - Record the solution implemented
   - Note any related improvements

3. **Present Results**
   - Explain what was fixed
   - Show before/after behavior
   - Ask: "Is the issue resolved? (saved to debug_report.md)"

4. **⏸️ STOP AND WAIT**
   - Wait for confirmation the fix works

Exit condition: When bug is fixed and confirmed working"""

    # Refactor mode workflow
    REFACTOR_MODE = """## REFACTOR MODE

User wants to improve existing code. Here's your workflow:

### Phase 1: Code Analysis
1. **Assess Current Code**
   - Analyze code structure and organization
   - Identify code smells and issues
   - Check for design pattern violations
   - Measure complexity and maintainability

2. **Identify Improvements**
   - List specific refactoring opportunities
   - Prioritize by impact and effort
   - Consider performance implications
   - Ensure no functionality changes

3. **Create Refactoring Plan**
   - Plan step-by-step improvements
   - Group related changes together
   - Identify potential risks
   - Plan testing strategy

### Phase 2: Execute Refactoring
1. **Apply Changes Incrementally**
   - Make one improvement at a time
   - Run tests after each change
   - Verify functionality preserved
   - Update documentation

2. **Save Refactoring Plan**
   - MANDATORY: Save refactor_plan.md
   - Document all planned improvements
   - Track completed changes
   - Note any unexpected issues

3. **Report Progress**
   - Show what was improved
   - Explain benefits achieved
   - Ask: "Are these improvements satisfactory? (saved to refactor_plan.md)"

4. **⏸️ STOP AND WAIT**
   - Wait for review and approval

Exit condition: When code is successfully refactored and approved"""

    # Feature mode workflow
    FEATURE_MODE = """## FEATURE MODE

User wants to add new functionality. Here's your workflow:

### Phase 1: Feature Analysis
1. **Understand Existing Codebase**
   - Analyze current architecture
   - Identify integration points
   - Understand existing patterns
   - Check for potential conflicts

2. **Feature Design**
   - Design feature architecture
   - Define interfaces and APIs
   - Plan implementation approach
   - Consider impact on existing code

3. **Implementation Planning**
   - Create implementation roadmap
   - Identify files to modify
   - Plan testing strategy
   - Estimate effort required

### Phase 2: Feature Implementation
1. **Implement New Feature**
   - Write new code following existing patterns
   - Modify existing code for integration
   - Add necessary configuration
   - Update documentation

2. **Integration and Testing**
   - Ensure feature integrates properly
   - Test with existing functionality
   - Handle edge cases
   - Verify performance impact

3. **Save Feature Documentation**
   - MANDATORY: Save feature_plan.md
   - Document feature design
   - Record implementation details
   - Note any modifications made

4. **Present Feature**
   - Demonstrate new functionality
   - Explain how it works
   - Ask: "Does this meet your requirements? (saved to feature_plan.md)"

5. **⏸️ STOP AND WAIT**
   - Wait for feature review and approval

Exit condition: When feature is implemented and working correctly"""

    # Review mode workflow
    REVIEW_MODE = """## REVIEW MODE

User requested code review. Here's your workflow:

### Phase 1: Comprehensive Analysis
1. **Code Quality Check**
   - Analyze code structure and patterns
   - Check for bugs and potential issues
   - Verify best practices adherence
   - Assess maintainability

2. **Security and Performance**
   - Check for security vulnerabilities
   - Identify performance bottlenecks
   - Review error handling
   - Assess scalability concerns

3. **Documentation and Testing**
   - Review code documentation
   - Check test coverage
   - Verify API documentation
   - Assess examples and usage

### Phase 2: Review Report
1. **Categorize Findings**
   - Group issues by severity
   - Prioritize critical issues
   - Provide actionable recommendations
   - Suggest specific improvements

2. **Save Review Report**
   - MANDATORY: Save code_review.md
   - Document all findings
   - Include code examples for issues
   - Provide improvement suggestions

3. **Present Review**
   - Summarize key findings
   - Highlight critical issues
   - Explain recommendations
   - Ask: "Shall I help implement these improvements? (saved to code_review.md)"

4. **⏸️ STOP AND WAIT**
   - Wait for feedback and next steps

Exit condition: When review is complete and next actions determined"""

    # Test mode workflow
    TEST_MODE = """## TEST MODE

User needs tests for the code. Here's your workflow:

### Phase 1: Test Strategy
1. **Analyze Code Structure**
   - Identify components to test
   - Determine test scenarios
   - Plan test organization
   - Choose testing framework

2. **Test Case Design**
   - Design unit tests for functions
   - Plan integration tests
   - Consider edge cases
   - Plan performance tests

3. **Test Implementation**
   - Write unit tests first
   - Add integration tests
   - Include error case tests
   - Create test utilities if needed

### Phase 2: Test Execution
1. **Run Test Suite**
   - Execute all tests
   - Check for failures
   - Measure code coverage
   - Analyze test results

2. **Save Test Plan**
   - MANDATORY: Save test_plan.md
   - Document test strategy
   - Record test cases
   - Note coverage metrics

3. **Report Results**
   - Show test coverage percentage
   - Report any failing tests
   - Explain test results
   - Ask: "Are the tests sufficient? (saved to test_plan.md)"

4. **⏸️ STOP AND WAIT**
   - Wait for test review and approval

Exit condition: When tests are comprehensive and passing"""

    # Implementation mode workflow
    IMPLEMENTATION_MODE = """## IMPLEMENTATION MODE

Ready to implement from approved specifications. Here's your workflow:

### Phase 1: Code Generation
1. **Follow Implementation Plan**
   - Reference specs.md requirements
   - Implement components systematically
   - Follow planned architecture
   - Maintain consistent patterns

2. **File-by-File Development**
   - Create files in logical order
   - Implement one component at a time
   - Include proper documentation
   - Test as you go

3. **Progressive Saving**
   - Save each file as completed
   - Update implementation_plan.md
   - Track progress against plan
   - Show incremental progress

### Phase 2: Code Assembly
1. **Integration**
   - Ensure components work together
   - Handle dependencies
   - Verify interfaces
   - Test overall functionality

2. **Final Review**
   - Check against specifications
   - Verify all requirements met
   - Ensure code quality
   - Document implementation

3. **Present Implementation**
   - Show completed code structure
   - Demonstrate functionality
   - Explain key implementation details
   - Ask: "Is the implementation complete and correct?"

4. **⏸️ STOP AND WAIT**
   - Wait for final approval

Exit condition: When implementation is complete and meeting specifications"""

    # Universal guidelines
    UNIVERSAL_GUIDELINES = """## UNIVERSAL GUIDELINES

### ⚠️ CRITICAL: Save-Then-Wait Rule
After saving each major artifact, you MUST STOP and WAIT:

1. **Specifications Phase:**
   - Create specs → Save specs.md → Ask for approval → STOP
   - Do not proceed without explicit approval

2. **Implementation Phase:**
   - Write code → Save files → Show progress → STOP at key points
   - Wait for review before next major component

3. **Debug Phase:**
   - Analyze → Save debug_report.md → Propose fix → STOP
   - Wait for approval to implement

### Code Quality Standards
- Write clean, readable, maintainable code
- Include meaningful comments and documentation
- Follow language-specific best practices
- Handle errors gracefully
- Consider performance implications

### Testing Philosophy
- Write tests for critical functionality
- Test edge cases and error conditions
- Ensure code works before presenting
- Document test coverage

### Communication Style
- Explain your reasoning and decisions
- Show code in context with surrounding code
- Ask clarifying questions when needed
- Provide options when multiple approaches exist

### File Organization
- Maintain logical directory structure
- Use consistent naming conventions
- Keep related code together
- Separate concerns appropriately

### Tool Usage Guidelines
- Use `read` to understand existing code
- Use `write` to create new files
- Use `edit` or `multi_edit` for modifications
- Use `bash` to run commands, tests, and builds
- Use `web_search` for research and documentation
- Use `list` and `glob` to navigate codebase
- Use `grep` to search within files"""

    # Tool usage guidelines
    TOOL_GUIDELINES = """## TOOL USAGE

### Available Tools
- **read**: Read existing files to understand code
- **write**: Create new files and save code
- **edit**: Make precise edits to existing files
- **multi_edit**: Apply multiple edits at once
- **list**: List directory contents
- **glob**: Find files with patterns
- **grep**: Search within files
- **bash**: Execute commands (compile, test, run)
  - **CRITICAL**: For servers/watchers, use `background=True` parameter
  - Examples: `bash(command="python -m http.server 8000", background=True)`
- **process_manager**: Control background processes
  - `list`: Show all running background processes
  - `status`: Check if specific process (PID) is running
  - `stop`: Gracefully stop a background process
  - `kill`: Force kill a background process
- **web_search**: Research documentation and solutions
- **web_fetch**: Get content from URLs
- **finish_task**: Mark work complete

### ⚠️ CRITICAL: Long-Running Commands

**ALWAYS use background=True for:**
- Development servers: `python -m http.server`, `flask run`, `uvicorn`, `npm start`
- Watchers: `npm run dev`, `nodemon`, `watch`
- Containers: `docker run` (without -d flag)

**Example:**
```python
# ❌ WRONG - This will hang/timeout!
bash(command="python -m http.server 8000")

# ✅ CORRECT - Run in background
bash(command="python -m http.server 8000", background=True)
# Returns immediately with PID, server runs in background
```

**Managing Background Processes:**
```python
# Start server in background
result = bash(command="uvicorn app:app", background=True)
# Returns: "Process ID (PID): 12345"

# List running processes
process_manager(operation="list")

# Check if still running
process_manager(operation="status", pid=12345)

# Stop when done
process_manager(operation="stop", pid=12345)
```

### Tool Usage Patterns by Mode

**Ideation Mode:**
- `read`, `list`, `web_search`, `web_fetch`, `write` (for specs.md)

**Implementation Mode:**
- All tools, especially `write`, `edit`, `multi_edit`, `bash`
- Use `bash` with `background=True` for servers during testing

**Debug Mode:**
- `read`, `grep`, `bash` (for running/debugging), `write`, `edit`

**Refactor Mode:**
- `read`, `write`, `edit`, `multi_edit`, `glob`, `grep`

**Feature Mode:**
- All tools for comprehensive development

**Review Mode:**
- `read`, `grep`, `web_search` (for standards), `write` (for report)

**Test Mode:**
- `read`, `write`, `bash` (test runner), `glob` (test discovery)
- `process_manager` to start/stop test servers

### File Paths
- All paths relative to session directory
- Use `src/` for source code
- Use `tests/` for test files
- Use `docs/` for documentation"""

    # Completion criteria
    COMPLETION_CRITERIA = """## COMPLETION CRITERIA

Call `finish_task` when you have delivered:

**Must Have:**
1. [DONE] Mode-specific objectives achieved
2. [DONE] All artifacts saved appropriately
3. [DONE] Code is working and tested
4. [DONE] Documentation provided
5. [DONE] User has reviewed and approved

**Before finishing:**
1. Confirm all requirements met
2. Ensure code quality standards
3. Verify tests pass
4. Provide summary of work
5. Ask if anything else is needed

**Success Message Example:**
"[SUCCESS] [Mode] completed successfully!
- Created: [files created]
- Modified: [files modified]
- Tests: [test status]
- Documentation: [docs created]
- Saved artifacts: [artifact files]

Would you like me to make any adjustments or help with next steps?" """

    def __init__(
        self,
        session_id: str,
        llm: LLMProvider,
        project_directory: Optional[str] = None,
        tools: Optional[ToolRegistry] = None,
        publish_callback: Optional[Callable[[BaseMessage], None]] = None,
        debug_log_path: Optional[str] = None
    ):
        """
        Initialize the Coding Agent V3.

        Args:
            session_id: The session identifier.
            llm: The LLM provider for intelligent conversation.
            project_directory: Directory for session files.
                              Defaults to data/sessions/{session_id}.
            tools: Optional custom tools. If None, uses all available tools.
            publish_callback: Callback for publishing messages to broker.
            debug_log_path: Optional path to debug log file.
        """

        # Define allowed tools
        self.allowed_tools = [
            "read", "write", "edit", "multi_edit",  # File operations
            "list", "glob", "grep",                # Navigation and search
            "bash",                                 # Command execution
            "process_manager",                      # Background process management
            "web_search", "web_fetch",             # Research capabilities
            "todo_read", "todo_write",             # Task management
            "finish_task"                          # Completion signal
        ]

        # Set additional attributes BEFORE calling parent constructor
        if tools is None:
            # Get all available tools from global registry
            from ..tools.all_tools import registry
            self.tools = registry
        else:
            self.tools = tools
        self.tool_registry = self.tools
        self.session_id = session_id
        # CodingV3 agent uses session_directory for all its files
        self.project_directory = project_directory
        self.publish_callback = publish_callback
        self.is_running = True
        self.sequence_counter = 0

        # System prompt caching
        self._session_state_hash: Optional[str] = None
        self._last_system_prompt: Optional[str] = None

        # Create project directory if it doesn't exist
        project_path = Path(self.project_directory)
        project_path.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        (project_path / "src").mkdir(exist_ok=True)
        (project_path / "tests").mkdir(exist_ok=True)
        (project_path / "docs").mkdir(exist_ok=True)

        # Create execution context with working directory
        self.execution_context = ExecutionContext(
            session_id=session_id,
            working_directory=str(project_path.resolve())
        )

        # Set execution context on all tools
        for tool in self.tools.list_tools():
            if hasattr(tool, 'execution_context'):
                tool.execution_context = self.execution_context

        # Call parent constructor
        super().__init__(
            llm=llm,
            config={
                "name": "CodingAgentV3",
                "version": "3.0.0",
                "session_id": session_id
            }
        )

        logger.info(
            f"CodingAgentV3 initialized for session {session_id}, "
            f"project: {self.project_directory}"
        )

    def step(self, message: BaseMessage) -> BaseMessage:
        """Process a single message."""
        if not self.is_running:
            return None

        # 1. Update Memory
        self._update_memory(message)

        # 2. Build system prompt (rebuilt each time, but cached when state unchanged)
        system_prompt = self._build_system_prompt()

        # 3. Generate response
        # Convert history to LLM format
        history_messages = self.history.to_llm_format()

        # Prepend system message to messages array (not stored in history)
        messages = [{"role": "system", "content": system_prompt}] + history_messages

        # Get tools schema
        tools_schema = self._get_tools_schema()

        # Call LLM
        response = self.llm.generate(messages, tools=tools_schema)

        # 4. Process Response
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

            return tool_msg
        else:
            # Create response message
            response_msg = LLMRespondMessage(
                session_id=self.session_id,
                sequence=self._next_sequence(),
                content=response.content
            )

            # Update history
            self._update_memory(response_msg)

            return response_msg

    def _update_memory(self, message: BaseMessage) -> None:
        """Update memory components based on the message."""
        self.history.add(message)

        # Update tracker if it's a tool result
        if isinstance(message, ToolResultObservation):
            # Find the matching tool call in history
            for msg in reversed(self.history.get_messages()):
                if isinstance(msg, ToolCallMessage):
                    for tc in msg.tool_calls:
                        if tc.id == message.call_id:
                            self.tracker.update(tc.tool_name, tc.arguments, message.content)
                            return

    def _next_sequence(self) -> int:
        """Get next sequence number."""
        seq = self.sequence_counter
        self.sequence_counter += 1
        return seq

    def _get_session_state_hash(self) -> str:
        """
        Generate hash of session state to detect when system prompt needs rebuilding.

        Returns:
            SHA256 hash string of current session state
        """
        session_path = Path(self.project_directory)

        # Collect state indicators
        state_indicators = []

        # Check for artifact files
        artifacts = [
            "specs.md", "implementation_plan.md", "debug_report.md",
            "refactor_plan.md", "feature_plan.md", "code_review.md", "test_plan.md"
        ]
        for artifact in artifacts:
            state_indicators.append(str((session_path / artifact).exists()))

        # Count files in key directories
        state_indicators.append(str(len(list(session_path.glob("src/*.*")))))
        state_indicators.append(str(len(list(session_path.glob("tests/*.*")))))
        state_indicators.append(str(len(list(session_path.glob("docs/*.*")))))

        # Hash the combined state
        state_string = "|".join(state_indicators)
        return hashlib.sha256(state_string.encode()).hexdigest()

    def get_system_message(self) -> str:
        """
        Public method to get the system message for external use.

        Returns:
            Complete system message with appropriate mode instructions
        """
        return self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        """
        Dynamically build system prompt based on current context with caching.

        The system prompt is rebuilt when the session state changes (new files created,
        artifacts saved, etc.). Otherwise, the cached version is returned.

        Returns:
            Complete system message with appropriate mode instructions
        """
        # Check if we can use cached system prompt
        current_hash = self._get_session_state_hash()
        if current_hash == self._session_state_hash and self._last_system_prompt:
            logger.debug("Using cached system prompt (session state unchanged)")
            return self._last_system_prompt

        logger.debug("Rebuilding system prompt (session state changed)")

        # Build the prompt parts
        prompt_parts = [
            self.CORE_IDENTITY.format(session_directory=self.project_directory),
            self.MODE_DETECTION,
        ]

        # Check what exists in session directory
        session_path = Path(self.project_directory)

        # Check for artifacts that indicate current mode
        has_specs = (session_path / "specs.md").exists()
        has_code = len(list(session_path.glob("src/*.*"))) > 0
        has_tests = len(list(session_path.glob("tests/*.*"))) > 0
        has_debug_report = (session_path / "debug_report.md").exists()
        has_refactor_plan = (session_path / "refactor_plan.md").exists()
        has_feature_plan = (session_path / "feature_plan.md").exists()
        has_code_review = (session_path / "code_review.md").exists()
        has_test_plan = (session_path / "test_plan.md").exists()
        has_impl_plan = (session_path / "implementation_plan.md").exists()

        # Determine current mode based on what exists and last message
        # For now, we'll default to checking most recent activity
        # In a real implementation, we might track the last mode used
        if not has_specs and not has_code:
            prompt_parts.append(self.IDEATION_MODE)
        elif has_specs and not has_code and not has_impl_plan:
            prompt_parts.append(self.IMPLEMENTATION_MODE)
        elif has_debug_report:
            prompt_parts.append(self.DEBUG_MODE)
        elif has_refactor_plan:
            prompt_parts.append(self.REFACTOR_MODE)
        elif has_feature_plan:
            prompt_parts.append(self.FEATURE_MODE)
        elif has_code_review:
            prompt_parts.append(self.REVIEW_MODE)
        elif has_test_plan:
            prompt_parts.append(self.TEST_MODE)
        elif has_code:
            # Default to refactor if code exists but no specific plan
            prompt_parts.append(self.REFACTOR_MODE)

        # Always include universal guidelines
        prompt_parts.extend([
            self.UNIVERSAL_GUIDELINES,
            self.TOOL_GUIDELINES,
            self.COMPLETION_CRITERIA
        ])

        # Add environment context
        prompt_parts.append(get_environment_context(working_directory=self.project_directory))

        # Add session-specific context
        prompt_parts.append(
            f"\n## Session Context\n"
            f"- Session ID: {self.session_id}\n"
            f"- Has Specifications: {has_specs}\n"
            f"- Has Source Code: {has_code}\n"
            f"- Has Tests: {has_tests}\n"
            f"- Has Debug Report: {has_debug_report}\n"
            f"- Has Refactor Plan: {has_refactor_plan}\n"
            f"- Has Feature Plan: {has_feature_plan}\n"
            f"- Has Code Review: {has_code_review}\n"
            f"- Has Test Plan: {has_test_plan}\n"
            f"- Has Implementation Plan: {has_impl_plan}"
        )

        # Build and cache the system prompt
        system_prompt = "\n\n".join(prompt_parts)
        self._session_state_hash = current_hash
        self._last_system_prompt = system_prompt

        return system_prompt

    def _get_tools_schema(self) -> list[dict]:
        """
        Get filtered tool schema for coding operations.

        Returns:
            List of tool schemas for allowed coding tools
        """
        # Get all available tools but filter to allowed ones
        all_tools = self.tools.to_llm_schema()
        filtered_tools = []

        for tool_schema in all_tools:
            tool_name = tool_schema.get("function", {}).get("name", "")
            if tool_name in self.allowed_tools:
                filtered_tools.append(tool_schema)

        return filtered_tools

    def _format_finish_message(self, reason: str, result: str) -> str:
        """
        Format finish message to include coding task details.

        Args:
            reason: Reason for finishing
            result: Summary of completed work

        Returns:
            Formatted message with coding details
        """
        return f"{reason}\n\n{result}"