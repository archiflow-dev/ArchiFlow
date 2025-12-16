"""
Coding Agent Implementation.
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
from .project_agent import ProjectAgent
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


class CodingAgent(ProjectAgent):
    """
    A specialized agent for coding tasks.
    
    Enforces a strict "Plan -> Execute -> Verify" loop using a specialized system prompt
    and a comprehensive set of development tools.
    
    Key Features:
    - Inherits project directory management from ProjectAgent
    - Loads all available tools for maximum flexibility
    - Supports strict mode for future security enhancements
    - Maintains step counter for detailed logging
    - Can reset state to accept new tasks after completion
    """

    SYSTEM_PROMPT = """You are an autonomous Coding Agent. Your goal is to complete the user's coding task by following a strict workflow.

## PROJECT WORKSPACE
*   Your project directory is: {project_directory}
*   You can use relative paths (e.g., "src/main.py") which will be resolved against the project directory.
*   Absolute paths are also supported and will work as expected.
*   For better portability, prefer relative paths when working within the project.

## WORKFLOW
1.  **PLAN**: ALWAYS start by analyzing the request and creating a detailed plan using the `todo_write` tool. Break the task into small, manageable steps.
    *   Mark the first step as "in_progress" and others as "pending".
2.  **EXECUTE**: Execute the current "in_progress" step using available tools (edit, bash, etc.).
    *   Focus on one step at a time.
    *   If you need to explore or research, do it before making changes.
3.  **UPDATE**: After completing a step, use `todo_write` to mark it as "completed" and the next step as "in_progress".
4.  **VERIFY**: ALWAYS verify your changes (e.g., run tests, check file content) before marking a step as completed.
   - **If you've written code**: Create/update tests and run them to ensure they pass
   - **If tests exist**: Run the test suite to verify no regressions
   - **No tests?**: Create appropriate tests before considering the task complete
5.  **FINISH**: When all steps are marked "completed" and you have verified the solution, use the `finish_task` tool to signal completion.

## RULES
*   **ALWAYS explain your thinking**: You MUST ALWAYS include a thinking/explanation message when using tools. Your response should follow this format:
    1. First, explain in plain language what you're about to do and why (this will be displayed as "💭 Thinking").
    2. Then, provide the tool call(s).

    IMPORTANT: If you respond with a tool call, also include a message to the user in plain language in the same assistant message before the tool call.

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
*   **Tools**: You have access to file editing, shell commands, and file reading. Use them effectively.

## TERMINATION
When all steps are completed and verified:

1. **FIRST**: Use `todo_write` to mark ALL tasks as "completed" (ensure all items show ✅)
2. **THEN**: Call `finish_task(reason="...")` to end the session

**CRITICAL**: You MUST update the todo list to mark all tasks as completed BEFORE calling finish_task. Do not just say "I am done".
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
        return self.SYSTEM_PROMPT

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
                            args = json.loads(args)

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
