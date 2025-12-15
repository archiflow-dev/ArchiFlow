"""Todo list reading tool (V2) for agents with priority and ID support."""
import json
import os
from typing import Dict, List, Optional
from pathlib import Path
from .tool_base import BaseTool, ToolResult


# Module-level storage for V2 todos (separate from V1)
_TODO_V2_STORAGE_PATH: Optional[Path] = None
_TODOS_V2: List[Dict] = []


class TodoReadV2Tool(BaseTool):
    """Tool for reading the current to-do list for the session (V2).

    This is an enhanced version that supports priority levels and unique IDs.
    It reads and displays the current todo list from the session storage.

    Use this tool frequently to:
    - Check what's pending at the beginning of conversations
    - Prioritize work before starting new tasks
    - Review progress when the user asks about tasks
    - Understand what to do next when uncertain
    - Update your understanding after completing tasks
    - Ensure you're on track after every few messages
    """

    name: str = "todo_read_v2"
    description: str = (
        "Reads the current to-do list (V2) for the session. Returns a list of todo items "
        "with their status, priority, content, and ID. Use this frequently to track "
        "progress and understand remaining work. Takes no parameters."
    )

    # Empty parameters object to indicate no input required
    parameters: Dict = {
        "type": "object",
        "properties": {},
        "required": []
    }

    @classmethod
    def _get_storage_path(cls) -> Path:
        """Get the path to the V2 todo storage file.

        Returns:
            Path to the todo storage JSON file
        """
        global _TODO_V2_STORAGE_PATH
        if _TODO_V2_STORAGE_PATH is None:
            home_dir = Path.home()
            storage_dir = home_dir / ".gpt_agent"
            storage_dir.mkdir(exist_ok=True)
            _TODO_V2_STORAGE_PATH = storage_dir / "todos_v2.json"
        return _TODO_V2_STORAGE_PATH

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
            pass

    @classmethod
    def set_todos(cls, todos: List[Dict]) -> None:
        """Set the current todo list (used by TodoWriteV2Tool).

        Args:
            todos: List of todo items with status, priority, content, and id
        """
        global _TODOS_V2
        _TODOS_V2 = todos
        cls._save_todos(todos)

    @classmethod
    def get_todos(cls) -> List[Dict]:
        """Get the current todo list.

        Returns:
            List of todo items
        """
        global _TODOS_V2
        if not _TODOS_V2:
            _TODOS_V2 = cls._load_todos()
        return _TODOS_V2

    @classmethod
    def clear_todos(cls) -> None:
        """Clear all todos from storage."""
        global _TODOS_V2
        _TODOS_V2 = []
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
        lines.append("Current Todo List (V2)")
        lines.append("=" * 70)
        lines.append("")

        # Count by status
        pending_count = sum(1 for t in todos if t.get("status") == "pending")
        in_progress_count = sum(1 for t in todos if t.get("status") == "in_progress")
        completed_count = sum(1 for t in todos if t.get("status") == "completed")

        # Count by priority
        high_count = sum(1 for t in todos if t.get("priority") == "high")
        medium_count = sum(1 for t in todos if t.get("priority") == "medium")
        low_count = sum(1 for t in todos if t.get("priority") == "low")

        lines.append(f"Summary: {len(todos)} total tasks")
        lines.append(f"\nStatus:")
        lines.append(f"  - Pending: {pending_count}")
        lines.append(f"  - In Progress: {in_progress_count}")
        lines.append(f"  - Completed: {completed_count}")
        lines.append(f"\nPriority:")
        lines.append(f"  - High: {high_count}")
        lines.append(f"  - Medium: {medium_count}")
        lines.append(f"  - Low: {low_count}")
        lines.append("")
        lines.append("-" * 70)
        lines.append("")

        # Group by status, then by priority within each status
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
        priority_symbols = {
            "high": "!!!",
            "medium": "!! ",
            "low": "!  "
        }

        for status in statuses:
            items = [t for t in todos if t.get("status") == status]
            if not items:
                continue

            # Sort by priority within status (high first)
            priority_order = {"high": 0, "medium": 1, "low": 2}
            items.sort(key=lambda x: priority_order.get(x.get("priority", "medium"), 1))

            label = status_labels.get(status, status.upper())
            lines.append(f"{label}:")
            lines.append("")

            for todo in items:
                symbol = status_symbols.get(status, "•")
                priority = todo.get("priority", "medium")
                priority_symbol = priority_symbols.get(priority, "!! ")
                content = todo.get("content", "(no content)")
                todo_id = todo.get("id", "no-id")[:8]  # Show first 8 chars of ID

                lines.append(f"  {symbol} {priority_symbol} {content}")
                lines.append(f"      ID: {todo_id}")

            lines.append("")

        # Add guidance
        lines.append("-" * 70)
        lines.append("")
        lines.append("Priority Legend: !!! = High, !!  = Medium, !   = Low")
        lines.append("")
        lines.append("Use this information to:")
        lines.append("  - Focus on high-priority tasks first")
        lines.append("  - Understand current progress and priorities")
        lines.append("  - Determine what to work on next")
        lines.append("  - Track completed work")
        lines.append("  - Ensure all tasks are addressed")

        return "\n".join(lines)

    async def execute(self) -> ToolResult:
        """Read and return the current todo list (V2).

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
                system_msg = "No todos exist yet. Create todos using the V2 todo management system when working on complex tasks."

            return ToolResult(output=output, system=system_msg)

        except Exception as e:
            return ToolResult(
                error=f"Error reading todo list: {type(e).__name__}: {str(e)}"
            )
