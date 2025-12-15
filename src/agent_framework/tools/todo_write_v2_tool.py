"""Todo list writing tool (V2) for agents with priority and ID support."""
import uuid
from typing import Dict, List, Literal
from .tool_base import BaseTool, ToolResult
from .todo_read_v2_tool import TodoReadV2Tool


class TodoWriteV2Tool(BaseTool):
    """Tool for creating and managing the to-do list for the session (V2).

    This is an enhanced version that includes priority levels and unique IDs
    for each task. Use this tool proactively when working on complex multi-step tasks.

    When to use:
    - Complex multi-step tasks requiring 3+ distinct steps
    - Non-trivial tasks requiring careful planning
    - When user provides multiple tasks to complete
    - After receiving new instructions
    - When starting work on a task (mark as in_progress)
    - After completing a task (mark as completed)

    When NOT to use:
    - Single, straightforward tasks
    - Trivial tasks with no organizational benefit
    - Tasks that can be completed in less than 3 trivial steps
    - Purely conversational or informational tasks

    Task states:
    - pending: Task not yet started
    - in_progress: Currently working on (limit to ONE task at a time)
    - completed: Task finished successfully

    Task priorities:
    - high: Critical tasks that should be done first
    - medium: Standard priority tasks
    - low: Nice-to-have tasks that can be done later

    Task completion requirements:
    - ONLY mark as completed when FULLY accomplished
    - Keep as in_progress if encountering errors or blockers
    - Never mark completed if tests fail, implementation is partial, or errors exist
    """

    name: str = "todo_write_v2"
    description: str = (
        "Creates or updates the to-do list for the session with priority levels and IDs. "
        "Takes a list of todo items with status (pending/in_progress/completed), "
        "priority (high/medium/low), content, and optional id. Use proactively for complex tasks."
    )

    parameters: Dict = {
        "type": "object",
        "properties": {
            "todos": {
                "type": "array",
                "description": "The complete updated todo list",
                "items": {
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "The task description",
                            "minLength": 1
                        },
                        "status": {
                            "type": "string",
                            "enum": ["pending", "in_progress", "completed"],
                            "description": "Task status: pending, in_progress, or completed"
                        },
                        "priority": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                            "description": "Task priority: high, medium, or low"
                        },
                        "id": {
                            "type": "string",
                            "description": "Optional unique identifier for the task. Auto-generated if not provided."
                        }
                    },
                    "required": ["content", "status", "priority"]
                }
            }
        },
        "required": ["todos"]
    }

    async def execute(self, todos: List[Dict]) -> ToolResult:
        """Update the todo list (V2).

        Args:
            todos: List of todo items with content, status, priority, and optional id

        Returns:
            ToolResult with success message or error
        """
        try:
            # Validate todos structure
            if not isinstance(todos, list):
                return ToolResult(
                    error="todos must be a list"
                )

            # Track generated IDs to ensure uniqueness
            used_ids = set()

            # Validate each todo item
            for i, todo in enumerate(todos):
                if not isinstance(todo, dict):
                    return ToolResult(
                        error=f"Todo item {i} must be an object"
                    )

                # Check required fields
                if "content" not in todo:
                    return ToolResult(
                        error=f"Todo item {i} missing required field 'content'"
                    )
                if "status" not in todo:
                    return ToolResult(
                        error=f"Todo item {i} missing required field 'status'"
                    )
                if "priority" not in todo:
                    return ToolResult(
                        error=f"Todo item {i} missing required field 'priority'"
                    )

                # Validate status
                valid_statuses = ["pending", "in_progress", "completed"]
                if todo["status"] not in valid_statuses:
                    return ToolResult(
                        error=f"Todo item {i} has invalid status '{todo['status']}'. "
                        f"Must be one of: {', '.join(valid_statuses)}"
                    )

                # Validate priority
                valid_priorities = ["high", "medium", "low"]
                if todo["priority"] not in valid_priorities:
                    return ToolResult(
                        error=f"Todo item {i} has invalid priority '{todo['priority']}'. "
                        f"Must be one of: {', '.join(valid_priorities)}"
                    )

                # Validate content is not empty
                if not todo["content"].strip():
                    return ToolResult(
                        error=f"Todo item {i} has empty content"
                    )

                # Generate ID if not provided
                if "id" not in todo or not todo["id"]:
                    todo["id"] = str(uuid.uuid4())

                # Check for duplicate IDs
                if todo["id"] in used_ids:
                    return ToolResult(
                        error=f"Todo item {i} has duplicate id '{todo['id']}'"
                    )
                used_ids.add(todo["id"])

            # Check that only one task is in_progress
            in_progress_count = sum(1 for t in todos if t["status"] == "in_progress")
            if in_progress_count > 1:
                return ToolResult(
                    error=f"Only ONE task can be in_progress at a time. Found {in_progress_count} tasks marked as in_progress."
                )

            # Save the todos
            TodoReadV2Tool.set_todos(todos)

            # Build success message
            pending_count = sum(1 for t in todos if t["status"] == "pending")
            in_progress_count = sum(1 for t in todos if t["status"] == "in_progress")
            completed_count = sum(1 for t in todos if t["status"] == "completed")

            # Count by priority
            high_count = sum(1 for t in todos if t["priority"] == "high")
            medium_count = sum(1 for t in todos if t["priority"] == "medium")
            low_count = sum(1 for t in todos if t["priority"] == "low")

            output = f"Todo list updated successfully.\n"
            output += f"Total: {len(todos)} tasks\n"
            output += f"\nStatus:\n"
            output += f"  - Pending: {pending_count}\n"
            output += f"  - In Progress: {in_progress_count}\n"
            output += f"  - Completed: {completed_count}\n"
            output += f"\nPriority:\n"
            output += f"  - High: {high_count}\n"
            output += f"  - Medium: {medium_count}\n"
            output += f"  - Low: {low_count}"

            # Add current task info
            if in_progress_count == 1:
                current_task = next(t for t in todos if t["status"] == "in_progress")
                output += f"\n\nCurrently working on: {current_task['content']}"
                output += f" (priority: {current_task['priority']})"

            return ToolResult(output=output)

        except Exception as e:
            return ToolResult(
                error=f"Error updating todo list: {type(e).__name__}: {str(e)}"
            )
