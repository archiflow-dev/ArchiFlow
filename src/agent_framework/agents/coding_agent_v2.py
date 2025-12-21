"""
Coding Agent V2 Implementation - Based on Claude Code's system prompt.
"""
import logging
from typing import Optional, List, Dict, Any, Callable
from datetime import datetime
import json
import os
from pathlib import Path

from ..messages.types import BaseMessage, UserMessage, AgentFinishedMessage
from ..tools.tool_base import ToolRegistry
from ..llm.provider import LLMProvider
from .project_agent import ProjectAgent, get_environment_context
from ..tools.all_tools import get_tool_collection

logger = logging.getLogger(__name__)


def _backup_existing_pr_description(review_dir: Path) -> None:
    """
    Backup existing pr_description.md to history folder with timestamp.

    Args:
        review_dir: Path to the review directory
    """
    pr_file = review_dir / "pr_description.md"

    if pr_file.exists():
        try:
            # Create history directory if it doesn't exist
            history_dir = review_dir / "history"
            history_dir.mkdir(exist_ok=True)

            # Create timestamped backup filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = history_dir / f"pr_description_{timestamp}.md"

            # Read original content
            original_content = pr_file.read_text(encoding='utf-8')

            # Add backup header with original file info
            backup_header = f"""# Backup of pr_description.md

**Original file**: .agent/review/pr_description.md
**Backup timestamp**: {datetime.now().isoformat()}
**Reason**: New PR description being generated

---

"""

            # Write to backup file
            backup_file.write_text(backup_header + original_content, encoding='utf-8')
            logger.info(f"Backed up existing pr_description.md to {backup_file}")

        except Exception as e:
            logger.error(f"Failed to backup existing pr_description.md: {e}")

class CodingAgentV2(ProjectAgent):
    """
    Coding Agent V2 - A specialized agent for coding tasks based on Claude Code.

    This agent uses Claude Code's system prompt and follows its principles:
    - Concise, direct responses
    - Proactive task management with TodoWrite
    - Focus on doing rather than explaining
    - Security-conscious (defensive only)
    - Minimal verbosity while maintaining helpfulness

    Key Features:
    - Inherits project directory management from ProjectAgent
    - Loads all available tools for maximum flexibility
    - Uses Claude Code's system prompt and behavior patterns
    - Maintains step counter for detailed logging
    - Can reset state to accept new tasks after completion
    """

    SYSTEM_PROMPT = """You are an autonomous Coding Agent integrated into ArchiFlow.

You are an interactive CLI tool that helps users with software engineering tasks.
Use the instructions below and the tools available to you to assist the user.

IMPORTANT: Assist with defensive security tasks only. Refuse to create, modify, or improve code
that may be used maliciously. Allow security analysis, detection rules, vulnerability explanations,
defensive tools, and security documentation.

IMPORTANT: You must NEVER generate or guess URLs for the user unless you are confident that the URLs are
for helping the user with programming. You may use URLs provided by the user in their messages or local files.

## Tone and style
You should be concise, direct, and to the point.
You MUST answer concisely with fewer than 4 lines (not including tool use or code generation), unless user asks for detail.
IMPORTANT: You should minimize output tokens as much as possible while maintaining helpfulness, quality,
and accuracy. Only address the specific query or task at hand, avoiding tangential information unless
absolutely critical for completing the request. If you can answer in 1-3 sentences or a short paragraph,
please do.
IMPORTANT: You should NOT answer with unnecessary preamble or postamble (such as explaining your code or
summarizing your action), unless the user asks you to.
Do not add additional code explanation summary unless requested by the user. After working on a file, just stop,
rather than providing an explanation of what you did.
Answer the user's question directly, without elaboration, explanation, or details. One word answers are best.
Avoid introductions, conclusions, and explanations. You MUST avoid text before/after your response, such as
"The answer is <answer>.", "Here is the content of the file..." or "Based on the information provided, the answer
is..." or "Here is what I will do next...".

Remember that your output will be displayed on a command line interface. Your responses can use
Github-flavored markdown for formatting, and will be rendered in a monospace font using the CommonMark specification.
Output text to communicate with the user; all text you output outside of tool use is displayed to the user.
Only use tools to complete tasks. Never use tools like Bash or code comments as means to communicate with the
user during the session.

If you cannot or will not help the user with something, please do not say why or what it could lead to,
since this comes across as preachy and annoying. Please offer helpful alternatives if possible,
and otherwise keep your response to 1-2 sentences.
Only use emojis if the user explicitly requests it. Avoid using emojis in all communication unless asked.
IMPORTANT: Keep your responses short, since they will be displayed on a command line interface.

## Proactiveness
You are allowed to be proactive, but only when the user asks you to do something.
You should strive to strike a balance between:
- Doing the right thing when asked, including taking actions and follow-up actions
- Not surprising the user with actions you take without asking

For example, if the user asks you how to approach something, you should do your best to answer
their question first, and not immediately jump into taking actions.

## Following conventions
When making changes to files, first understand the file's code conventions. Mimic code style,
use existing libraries and utilities, and follow existing patterns.
- NEVER assume that a given library is available, even if it is well known. Whenever you write code that uses
  a library or framework, first check that this codebase already uses the given library. For example,
  you might look at neighboring files, or check the package.json (or cargo.toml, and so on depending on the language).
- When you create a new component, first look at existing components to see how they're written; then consider
  framework choice, naming conventions, typing, and other conventions.
- When you edit a piece of code, first look at the code's surrounding context (especially its imports)
  to understand the code's choice of frameworks and libraries. Then consider how to make the given change in
  a way that is most idiomatic.
- Always follow security best practices. Never introduce code that exposes or logs secrets and keys.
  Never commit secrets or keys to the repository.

## Code style
- IMPORTANT: DO NOT ADD ***ANY*** COMMENTS unless asked

## Task Management
You have access to the TodoWrite tools to help you manage and plan tasks. Use these tools VERY
frequently to ensure that you are tracking your tasks and giving the user visibility into your progress.
These tools are also EXTREMELY helpful for planning tasks, and for breaking down larger complex tasks into
smaller steps.

It is critical that you mark todos as completed as soon as you are done with a task. Do not batch up
multiple tasks before marking them as completed.

Examples:
     <example>
       user: Run the build and fix any type errors
       assistant: I\'m going to use the TodoWrite tool to write the following items to the todo list: 
       - Run the build
       - Fix any type errors
       
       I\'m now going torun the build using Bash.
       
       Looks like I found 10 type errors. I\'m going to use the TodoWrite tool to write 10 items to the todo list.
       
       marking the first todo as in_progress
       
       Let me start working on the first item...
       
       The first item has been fixed, let me mark the first todo as completed, and move on to the 
       second item...
       ..
       ..
     </example>
     In the above example, the assistant completes all the tasks, including the 10 error fixes and running the 
     build and fixing allerrors.
     
     <example>
       user: Help me write a new feature that allows users to track their usage metrics and export them to various formats
       
       assistant: I\'ll help you implement a usage metrics tracking and export feature. Let me first use 
       the TodoWrite tool to plan this task.
       Adding the following todos to the todo list:
        1. Research existing metrics tracking in the codebase
        2. Design the metrics collection system
        3. Implement core metrics tracking functionality
        4. Create export functionality for different formats
        
       Let me start by researching the existing codebase to understand what metrics we might already be tracking 
       and howwe can build on that.

       I\'m going to search for any existing metrics or telemetry code in the project.

       I\'ve found some existing telemetry code. Let me mark the first todo as in_progress and start designing 
       our metrics tracking systembased on what I\'ve learned...
       
       [Assistant continues implementing the featurestep by step, marking todos as in_progress and completed as 
       they go]
     </example>

## PROJECT WORKSPACE
*   Your project directory is: {project_directory}
*   You can use relative paths (e.g., "src/main.py") which will be resolved against the project directory.
*   Absolute paths are also supported and will work as expected.
*   For better portability, prefer relative paths when working within the project.

## Doing tasks
The user will primarily request you perform software engineering tasks. This includes solving bugs, adding
new functionality, refactoring code, explaining code, and more. For these tasks the following steps are recommended:
- Use the TodoWrite tool to plan the task if required
- Use the available search tools to understand the codebase and the user's query. You are encouraged to
  use the search tools extensively both in parallel and sequentially.
- Implement the solution using all tools available to you
- Verify the solution if possible with tests. NEVER assume specific test framework or test script.
  Check the README or search codebase to determine the testing approach.
- VERY IMPORTANT: When you have completed a task, you MUST run the lint and typecheck commands
  (eg. npm run lint, npm run typecheck, ruff, etc.) with Bash if they were provided to you to ensure
  your code is correct. If you are unable to find the correct command, ask the user for the command
  to run and if they supply it, proactively suggest writing it to CLAUDE.md so that you will know to run it next time.
  NEVER commit changes unless the user explicitly asks you to. It is VERY IMPORTANT to only commit when explicitly asked.

## Tool usage policy
- When doing file search, prefer to use the Task tool in order to reduce context usage.
- You should proactively use the Task tool with specialized agents when the task at hand matches the agent's description.
- You have the capability to call multiple tools in a single response. When multiple independent pieces of
  information are requested, batch your tool calls together for optimal performance. When making multiple bash
  tool calls, you MUST send a single message with multiple tools calls to run the calls in parallel.

## Code References
When referencing specific functions or pieces of code include the pattern `file_path:line_number` to allow the
user to easily navigate to the source code location.

## RULES
*   **ALWAYS explain your thinking**: IMPORTANT: If you respond with a tool call, you MUST also include a message to the user in plain language in the same assistant message before the tool call.
    Example: "I need to read the configuration file to understand the current settings. Let me check the config.json file."
    This is MANDATORY - every tool execution must be preceded by thinking.
*   **Use `todo_write` proactively**: The system relies on the todo list state. Update it frequently.
*   **Verification is mandatory**: Never assume your code works. Verify it.
*   **Testing is required**: Always create tests for your changes and ensure all tests pass before marking a task as completed. This includes:
    - Writing unit tests for new functionality
    - Running existing test suites to verify no regressions
    - Creating integration tests when appropriate
    - Verifying test coverage for critical paths
*   **Clarity**: If the user's request is unclear, you may ask for clarification, but try to resolve ambiguities yourself if possible.

## TERMINATION
When all steps are completed and verified:
1. FIRST: Use `todo_write` to mark ALL tasks as "completed" (ensure all items show ✅)
2. THEN: Call `finish_task(reason="...")` to end the session

**CRITICAL**: You MUST update the todo list to mark all tasks as completed BEFORE calling finish_task.
"""

    def __init__(
        self,
        session_id: str,
        llm: LLMProvider,
        project_directory: Optional[str] = None,
        tools: Optional[ToolRegistry] = None,
        publish_callback: Optional[Callable[[BaseMessage], None]] = None,
        strict_mode: bool = False,
        debug_log_path: Optional[str] = None
    ):
        """
        Initialize the Coding Agent.

        Args:
            session_id: The session identifier.
            llm: The LLM provider.
            project_directory: Root directory for the project. Relative paths
                              in tools will be resolved against this directory.
                              Defaults to current working directory if not specified.
            tools: Optional custom tools. If None, loads default set.
            publish_callback: Callback for publishing messages.
            strict_mode: If True, enforce all file operations within project_directory.
                        (Currently not enforced, reserved for future use)
            debug_log_path: Optional path to debug log file for saving LLM interactions.
                           If None, no debug logging is performed.
        """
        # Store CodingAgent-specific parameters
        self.strict_mode = strict_mode
        self.step_counter = 0
        self.pr_description_initialized = False

        # Track session start time for file change detection
        from datetime import datetime
        self.session_start_time = datetime.now()

        # Call parent constructor - handles all common initialization
        super().__init__(
            session_id=session_id,
            llm=llm,
            project_directory=project_directory,
            tools=tools,
            publish_callback=publish_callback,
            debug_log_path=debug_log_path,
            agent_name="CodingAgent",
            agent_version="1.0.0"
        )

    def get_system_message(self) -> str:
        """Return the system prompt for the coding agent."""
        # Format the system prompt with project directory
        prompt = self.SYSTEM_PROMPT.format(project_directory=self.project_directory)

        # Add environment context
        prompt += "\n\n" + get_environment_context(working_directory=str(self.project_directory))

        return prompt

    def _record_file_change(self, filepath: str):
        """
        Record a file modification during the session.

        Tracks files that have been modified by edit or write tools.
        Stores them in .agent/review/files_modified.json for use in
        PR description generation when not in a git repository.

        Args:
            filepath: Path to the file that was modified (can be absolute or relative)
        """
        from pathlib import Path
        import json

        try:
            # Ensure review directory exists
            review_dir = Path(self.project_directory) / ".agent" / "review"
            review_dir.mkdir(parents=True, exist_ok=True)

            changes_file = review_dir / "files_modified.json"

            # Load existing changes
            if changes_file.exists():
                with open(changes_file, 'r', encoding='utf-8') as f:
                    changes = json.load(f)
            else:
                changes = {
                    "session_id": self.session_id,
                    "session_start": self.session_start_time.isoformat(),
                    "files": []
                }

            # Convert filepath to relative path if possible
            try:
                file_path_obj = Path(filepath)
                if file_path_obj.is_absolute():
                    relative_path = str(file_path_obj.relative_to(self.project_directory))
                else:
                    relative_path = str(filepath)
            except (ValueError, OSError):
                # If file is outside project directory or other error, use as-is
                relative_path = str(filepath)

            # Add file if not already tracked
            if relative_path not in changes["files"]:
                changes["files"].append(relative_path)
                logger.info(f"Recorded file change: {relative_path}")

            # Save
            with open(changes_file, 'w', encoding='utf-8') as f:
                json.dump(changes, f, indent=2)

        except Exception as e:
            # Don't fail the operation if tracking fails
            logger.warning(f"Failed to record file change for {filepath}: {e}")

    def _get_tracked_file_changes(self) -> List[str]:
        """
        Get list of files modified during this session.

        Returns:
            List of relative file paths that were modified, or empty list if none tracked
        """
        from pathlib import Path
        import json

        try:
            changes_file = Path(self.project_directory) / ".agent" / "review" / "files_modified.json"

            if changes_file.exists():
                with open(changes_file, 'r', encoding='utf-8') as f:
                    changes = json.load(f)
                    return changes.get("files", [])
        except Exception as e:
            logger.warning(f"Failed to read tracked file changes: {e}")

        return []

    def _process_tool_calls(self, response: Any) -> Optional['BaseMessage']:
        """
        Override to track file modifications before processing tool calls.

        Intercepts edit and write tool calls to record which files are being modified.
        This allows us to track changes even in non-git repositories.

        Args:
            response: LLM response object with tool calls

        Returns:
            Result from parent _process_tool_calls
        """
        # Track file modifications from edit/write tools
        if response.tool_calls:
            for tc in response.tool_calls:
                try:
                    # Check if this is a file modification tool
                    if tc.name in ['edit', 'write', 'multi_edit']:
                        # Parse arguments
                        import json
                        args = tc.arguments
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except json.JSONDecodeError as je:
                                logger.error(f"Failed to parse tool arguments as JSON for {tc.name}")
                                logger.error(f"JSON error: {je}")
                                logger.error(f"Arguments (first 500 chars): {args[:500]}")
                                logger.error(f"Arguments around error position: {args[max(0, je.pos-50):je.pos+50]}")
                                raise

                        # Extract file path based on tool type
                        if tc.name in ['edit', 'write']:
                            filepath = args.get('file_path')
                            if filepath:
                                self._record_file_change(filepath)
                        elif tc.name == 'multi_edit':
                            # multi_edit has list of edits
                            edits = args.get('edits', [])
                            for edit in edits:
                                filepath = edit.get('file_path')
                                if filepath:
                                    self._record_file_change(filepath)
                except Exception as e:
                    # Don't fail tool execution if tracking fails
                    logger.warning(f"Failed to track file change for tool {tc.name}: {e}")

        # Call parent to process tool calls normally
        return super()._process_tool_calls(response)

    def _setup_tools(self):
        """
        Load all available tools for coding tasks.
        
        CodingAgent has access to all tools including:
        - File operations (edit, read, list)
        - Shell commands (bash)
        - TODO management (todo_write, todo_read)
        - Task control (finish_task)
        - And more...
        """
        default_collection = get_tool_collection()
        
        for tool in default_collection.tools:
            if not self.tools.get(tool.name):
                self.tools.register(tool)
        
        logger.info(f"CodingAgent loaded {len(self.tools.list_tools())} tools")

    def _get_tools_schema(self) -> List[Dict[str, Any]]:
        """
        Get all tools for LLM (no filtering).
        
        CodingAgent exposes all available tools to maximize flexibility.
        
        Returns:
            List of all tool schemas in OpenAI format
        """
        return self.tools.to_llm_schema()

    def _handle_finish_task(self, tool_calls: List[Any]) -> Optional['AgentFinishedMessage']:
        """
        Override to generate final PR description before finishing.

        Phase 1.5: When finish_task is called, this will:
        1. Generate final PR description via LLM
        2. Save to .agent/review/pr_description.md
        3. Call parent to complete finish workflow

        Args:
            tool_calls: List of tool calls from LLM response

        Returns:
            AgentFinishedMessage if finish_task found, None otherwise
        """
        # Check if finish_task is in tool_calls
        has_finish_task = any(tc.name == "finish_task" for tc in tool_calls)

        if has_finish_task:
            # Generate final PR description before finishing
            try:
                pr_description = self._generate_final_pr_description()
                logger.info(f"Generated final PR description: {len(pr_description)} characters")
            except Exception as e:
                logger.error(f"Failed to generate PR description: {e}")
                # Continue with finish even if PR description fails

        # Call parent to handle finish_task normally
        return super()._handle_finish_task(tool_calls)

    def step(self, message: BaseMessage) -> Optional[BaseMessage]:
        """
        Process message with CodingAgent-specific logic.
        
        Adds reset logic: if agent has finished but receives a new UserMessage,
        it will reset to accept the new task while preserving history and TODO lists.
        
        Args:
            message: Incoming message (UserMessage or ToolResultObservation)
            
        Returns:
            Response message or None
        """
        # Save PR description draft on first user message  
        if not self.pr_description_initialized and isinstance(message, UserMessage):
            if message.content:
                self._initialize_pr_description_draft(message.content)
                self.pr_description_initialized = True
        
        # Reset state if we receive a new UserMessage after finishing
        if not self.is_running and isinstance(message, UserMessage):
            logger.info("Agent was finished, resetting state for new task")
            self.is_running = True
            # Note: We preserve history and TODO lists across tasks

        # Increment step counter for debug logging
        self.step_counter += 1

        # Call parent for standard message processing
        return super().step(message)
    
    def _initialize_pr_description_draft(self, user_request: str):
        """
        Initialize PR description draft when task starts.
        
        Saves the initial user request to .agent/review/pr_description.draft.md
        for future use by CodeReviewAgent.
        
        Args:
            user_request: The user's initial request/task description.
        """
        from pathlib import Path
        from datetime import datetime
        import json
        
        # Ensure review directory exists
        review_dir = Path(self.project_directory) / ".agent" / "review"
        review_dir.mkdir(parents=True, exist_ok=True)
        
        # Create draft PR description
        draft_content = f"""# PR Description (Draft)

**Created**: {datetime.now().isoformat()}
**Session**: {self.session_id}
**Agent**: CodingAgent

## What was requested
{user_request}

## Implementation Progress
[Will be updated as work progresses]

## Changes
[TODO list will be tracked here]

---
*Draft - final description will be generated at task completion*
"""
        
        # Save draft file
        draft_file = review_dir / "pr_description.draft.md"
        draft_file.write_text(draft_content, encoding='utf-8')
        
        # Update metadata
        metadata_file = review_dir / "metadata.json"
        if metadata_file.exists():
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
        else:
            metadata = {
                "created": datetime.now().isoformat(),
                "reviews": []
            }
        
        metadata["pr_description"] = {
            "file": "pr_description.draft.md",
            "created_by": self.session_id,
            "created_at": datetime.now().isoformat(),
            "source": "user_request",
            "is_draft": True
        }
        metadata["last_updated"] = datetime.now().isoformat()
        
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"Initialized PR description draft at {draft_file}")
    
    def _generate_final_pr_description(self) -> str:
        """
        Generate final PR description using LLM at task completion.
        
        Returns:
            Generated PR description content.
        """
        from pathlib import Path
        from datetime import datetime
        import json
        
        review_dir = Path(self.project_directory) / ".agent" / "review"
        context = self._gather_pr_context()
        
        # Create LLM prompt in messages format
        files_list = context['files_changed']
        if files_list:
            files_section = '\n'.join([f"- {f}" for f in files_list])
        else:
            files_section = "No files were changed"

        prompt = f"""Generate a professional Pull Request description for this completed work.

**Original Request:** {context['original_request']}

**Completed Work:**
{self._format_todos_for_pr(context['todos_completed'])}

**Files Changed:**
{files_section}

IMPORTANT INSTRUCTIONS:
1. Create a comprehensive PR description with these sections: Summary, Changes, Implementation Details, Testing
2. MUST include the original request in the Summary section
3. Be professional, accurate, and include technical details
4. CRITICAL: ONLY mention files that are listed in the "Files Changed" section above
5. DO NOT make up, invent, or assume any file names that are not explicitly listed
6. If no files are listed, state "No file changes detected" in the Changes section
7. Focus on describing the work done based on the completed tasks, not on inventing file details

Generate the PR description now:"""

        # Generate via LLM with fallback
        try:
            messages = [{"role": "user", "content": prompt}]
            response = self.llm.generate(messages)  # Use default temperature
            pr_description = response.content
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            pr_description = self._generate_fallback_pr_description(context)
  
        # Save (ensure directory exists)
        review_dir.mkdir(parents=True, exist_ok=True)

        # Backup existing PR description if it exists
        _backup_existing_pr_description(review_dir)

        pr_file = review_dir / "pr_description.md"
        pr_file.write_text(pr_description, encoding='utf-8')
        
        # Update metadata
        metadata_file = review_dir / "metadata.json"
        metadata = json.load(open(metadata_file)) if metadata_file.exists() else {"reviews": []}
        metadata["pr_description"] = {
            "file": "pr_description.md",
            "created_by": self.session_id,
            "created_at": datetime.now().isoformat(),
            "source": "llm_generated",
            "is_draft": False
        }
        metadata["last_updated"] = datetime.now().isoformat()
        json.dump(metadata, open(metadata_file, 'w'), indent=2)
        
        logger.info(f"Generated PR description ({len(pr_description)} chars)")
        return pr_description
    
    def _gather_pr_context(self) -> dict:
        """
        Gather context for PR description generation.

        Collects:
        - Original request from draft PR description
        - Completed TODOs
        - Changed files (tries git first, falls back to tracked changes)

        Returns:
            Dictionary with original_request, todos_completed, and files_changed
        """
        from pathlib import Path
        import subprocess

        review_dir = Path(self.project_directory) / ".agent" / "review"
        original_request = "Task completed"

        # Get from draft
        draft_file = review_dir / "pr_description.draft.md"
        if draft_file.exists():
            content = draft_file.read_text()
            if "## What was requested" in content:
                original_request = content.split("## What was requested")[1].split("##")[0].strip()

        # Get TODOs
        todos = []
        todo_file = Path(self.project_directory) / ".agent" / "todos.json"
        if todo_file.exists():
            import json
            with open(todo_file) as f:
                data = json.load(f)
                todos = [t.get('content', '') for t in data if t.get('status') == 'completed']
            logger.info(f"Found {len(todos)} completed todos")
            for i, todo in enumerate(todos, 1):
                logger.info(f"  Todo {i}: {todo}")
        else:
            logger.debug(f"TODO file not found at {todo_file} (will be created when agent uses todo_write)")

        # Get changed files - try git first, then fallback to tracked changes
        files_changed = []
        git_available = False

        try:
            # Try git commands first (most reliable for git repos)
            logger.info("Attempting to detect file changes via git...")
            for cmd in [["git", "diff", "--name-only"], ["git", "diff", "--cached", "--name-only"]]:
                result = subprocess.run(
                    cmd,
                    cwd=self.project_directory,
                    capture_output=True,
                    text=True,
                    check=False
                )
                if result.returncode == 0:
                    git_available = True
                    files_changed.extend([f.strip() for f in result.stdout.split('\n') if f.strip()])

            if git_available:
                files_changed = list(set(files_changed))
                logger.info(f"[GIT] Found {len(files_changed)} changed files via git")
                for i, file in enumerate(files_changed, 1):
                    logger.info(f"  [GIT] File {i}: {file}")
            else:
                logger.info("Git is not available or not initialized in this directory")
        except Exception as e:
            logger.warning(f"Git commands failed: {e}")

        # Fallback: Use tracked file modifications for non-git repos
        if not files_changed:
            logger.info("No git changes detected, attempting to use file tracking...")
            files_changed = self._get_tracked_file_changes()
            if files_changed:
                logger.info(f"[TRACKING] Found {len(files_changed)} changed files via file tracking (non-git repo)")
                for i, file in enumerate(files_changed, 1):
                    logger.info(f"  [TRACKING] File {i}: {file}")
            else:
                logger.warning("No changed files detected via git or tracking - PR description may be incomplete")

        # Log final PR context summary
        logger.info("=== PR Context Summary ===")
        logger.info(f"Original request: {original_request[:100]}{'...' if len(original_request) > 100 else ''}")
        logger.info(f"Completed todos: {len(todos)}")
        logger.info(f"Files changed: {len(files_changed)}")
        logger.info("=========================")

        return {
            "original_request": original_request,
            "todos_completed": todos,
            "files_changed": files_changed
        }
    
    def _format_todos_for_pr(self, todos: list) -> str:
        """Format TODOs for PR description."""
        return '\n'.join([f"- ✅ {t}" for t in todos]) if todos else "- Task completed"
    
    def _generate_fallback_pr_description(self, context: dict) -> str:
        """Fallback PR description template."""
        from datetime import datetime
        return f"""# Pull Request

**Generated**: {datetime.now().isoformat()}

## Summary
{context['original_request']}

## Changes
{self._format_todos_for_pr(context['todos_completed'])}

## Files Modified
{chr(10).join([f"- {f}" for f in context['files_changed']]) if context['files_changed'] else '- None'}

---
*Auto-generated PR description*
"""