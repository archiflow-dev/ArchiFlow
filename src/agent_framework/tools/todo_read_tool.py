"""Todo list reading tool for agents."""
import json
import os
from typing import Dict, List, Optional
from pathlib import Path
from .tool_base import BaseTool, ToolResult


# Module-level storage for todos (shared across instances in same process)
# Must be outside the class to avoid Pydantic interference
_TODO_STORAGE_PATH: Optional[Path] = None
_TODOS: List[Dict] = []


class TodoReadTool(BaseTool):
    """Tool for reading the current to-do list for the session.

    This tool reads and displays the current todo list from the session storage.
    It should be used proactively and frequently to track task progress and
    understand what work remains.

    Use this tool:
    - At the beginning of conversations to see what's pending
    - Before starting new tasks to prioritize work
    - When the user asks about previous tasks or plans
    - Whenever you're uncertain about what to do next
    - After completing tasks to update your understanding
    - After every few messages to ensure you're on track
    """

    name: str = "todo_read"
    description: str = (
        "Reads the current to-do list for the session. Returns a list of todo items "
        "with their status, priority, and content. Use this frequently to track "
        "progress and understand remaining work. Takes no parameters."
    )

    # Important: Empty parameters object to indicate no input required
    parameters: Dict = {
        "type": "object",
        "properties": {},
        "required": []
    }

    @classmethod
    def _get_storage_path(cls) -> Path:
        """Get the path to the todo storage file.

        Returns:
            Path to the todo storage JSON file
        """
        global _TODO_STORAGE_PATH
        if _TODO_STORAGE_PATH is None:
            # Store in a temp directory or user's home directory
            home_dir = Path.home()
            storage_dir = home_dir / ".gpt_agent"
            storage_dir.mkdir(exist_ok=True)
            _TODO_STORAGE_PATH = storage_dir / "todos.json"
        return _TODO_STORAGE_PATH

    @classmethod
    def _load_todos(cls) -> List[Dict]:
        """Load todos from storage.

        Returns:
            List of todo items
        """
        storage_path = cls._get_storage_path()

        if not storage_path.exists():
            return []

        try:
            with open(storage_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("todos", [])
        except (json.JSONDecodeError, IOError):
            return []

    @classmethod
    def _save_todos(cls, todos: List[Dict]) -> None:
        """Save todos to storage.

        Args:
            todos: List of todo items to save
        """
        storage_path = cls._get_storage_path()

        try:
            with open(storage_path, 'w', encoding='utf-8') as f:
                json.dump({"todos": todos}, f, indent=2, ensure_ascii=False)
        except IOError:
            pass  # Silently fail if we can't write

    @classmethod
    def set_todos(cls, todos: List[Dict]) -> None:
        """Set the current todo list (used by TodoWriteTool).

        Args:
            todos: List of todo items with status, content, and activeForm
        """
        global _TODOS
        _TODOS = todos
        cls._save_todos(todos)

    @classmethod
    def get_todos(cls) -> List[Dict]:
        """Get the current todo list.

        Returns:
            List of todo items
        """
        global _TODOS
        # Try to load from storage if in-memory list is empty
        if not _TODOS:
            _TODOS = cls._load_todos()
        return _TODOS

    @classmethod
    def clear_todos(cls) -> None:
        """Clear all todos from storage."""
        global _TODOS
        _TODOS = []
        storage_path = cls._get_storage_path()
        if storage_path.exists():
            try:
                storage_path.unlink()
            except IOError:
                pass

    def _format_todo_list(self, todos: List[Dict]) -> str:
        """Format the todo list for display.

        Args:
            todos: List of todo items

        Returns:
            Formatted string representation
        """
        if not todos:
            return "No todos in the current session."

        lines = []
        lines.append("Current Todo List")
        lines.append("=" * 70)
        lines.append("")

        # Count by status
        pending_count = sum(1 for t in todos if t.get("status") == "pending")
        in_progress_count = sum(1 for t in todos if t.get("status") == "in_progress")
        completed_count = sum(1 for t in todos if t.get("status") == "completed")

        lines.append(f"Summary: {len(todos)} total tasks")
        lines.append(f"  - Pending: {pending_count}")
        lines.append(f"  - In Progress: {in_progress_count}")
        lines.append(f"  - Completed: {completed_count}")
        lines.append("")
        lines.append("-" * 70)
        lines.append("")

        # Group by status
        statuses = ["in_progress", "pending", "completed"]
        status_labels = {
            "pending": "PENDING",
            "in_progress": "IN PROGRESS",
            "completed": "COMPLETED"
        }
        status_symbols = {
            "pending": "[ ]",
            "in_progress": "[~]",
            "completed": "[x]"
        }

        for status in statuses:
            items = [t for t in todos if t.get("status") == status]
            if not items:
                continue

            label = status_labels.get(status, status.upper())
            lines.append(f"{label}:")
            lines.append("")

            for i, todo in enumerate(items, 1):
                symbol = status_symbols.get(status, "•")
                content = todo.get("content", "(no content)")

                # Calculate the actual index in the full list
                actual_index = todos.index(todo) + 1

                lines.append(f"  {symbol} [{actual_index}] {content}")

                # Show active form if in progress
                if status == "in_progress" and "activeForm" in todo:
                    active_form = todo.get("activeForm", "")
                    if active_form and active_form != content:
                        lines.append(f"      -> {active_form}")

            lines.append("")

        # Add guidance
        lines.append("-" * 70)
        lines.append("")
        lines.append("Use this information to:")
        lines.append("  - Understand current progress and priorities")
        lines.append("  - Determine what to work on next")
        lines.append("  - Track completed work")
        lines.append("  - Ensure all tasks are addressed")

        return "\n".join(lines)

    async def execute(self) -> ToolResult:
        """Read and return the current todo list.

        This method takes no parameters.

        Returns:
            ToolResult with formatted todo list or empty list message
        """
        try:
            # Load current todos
            todos = self.get_todos()

            # Format the output
            output = self._format_todo_list(todos)

            # Add system message if list is empty
            system_msg = None
            if not todos:
                system_msg = "No todos exist yet. Create todos using the todo management system when working on complex tasks."

            return ToolResult(output=output, system=system_msg)

        except Exception as e:
            return ToolResult(
                error=f"Error reading todo list: {type(e).__name__}: {str(e)}"
            )
