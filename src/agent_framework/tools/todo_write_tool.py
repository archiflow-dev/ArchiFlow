"""Todo list writing tool for agents."""
from typing import Dict, List, Literal
from pydantic import Field
from .tool_base import BaseTool, ToolResult
from .todo_read_tool import TodoReadTool


class TodoItem(Dict):
    """A todo item with content, status, and active form."""
    content: str
    status: Literal["pending", "in_progress", "completed"]
    activeForm: str


class TodoWriteTool(BaseTool):
    """Tool for creating and managing the to-do list for the session.

    This tool allows agents to create, update, and manage todo items.
    Use this tool proactively when working on complex multi-step tasks.

    When to use:
    - Complex multi-step tasks requiring 3+ distinct steps
    - Non-trivial tasks requiring careful planning
    - When user provides multiple tasks to complete
    - After receiving new instructions
    - When starting work on a task (mark as in_progress)
    - After completing a task (mark as completed)

    Task states:
    - pending: Task not yet started
    - in_progress: Currently working on (limit to ONE task at a time)
    - completed: Task finished successfully

    Task descriptions must have two forms:
    - content: Imperative form (e.g., "Run tests", "Build the project")
    - activeForm: Present continuous form (e.g., "Running tests", "Building the project")
    """

    name: str = "todo_write"
    description: str = (
        "Creates or updates the to-do list for the session. Takes a list of todo items "
        "with status (pending/in_progress/completed), content (imperative), and "
        "activeForm (present continuous). Use proactively for complex tasks."
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
                            "description": "The task description in imperative form (e.g., 'Run tests')",
                            "minLength": 1
                        },
                        "status": {
                            "type": "string",
                            "enum": ["pending", "in_progress", "completed"],
                            "description": "Task status: pending, in_progress, or completed"
                        },
                        "activeForm": {
                            "type": "string",
                            "description": "The task description in present continuous form (e.g., 'Running tests')",
                            "minLength": 1
                        }
                    },
                    "required": ["content", "status", "activeForm"]
                }
            }
        },
        "required": ["todos"]
    }

    async def execute(self, todos: List[Dict]) -> ToolResult:
        """Update the todo list.

        Args:
            todos: List of todo items with content, status, and activeForm

        Returns:
            ToolResult with success message or error
        """
        try:
            # Validate todos structure
            if not isinstance(todos, list):
                return ToolResult(
                    error="todos must be a list"
                )

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
                if "activeForm" not in todo:
                    return ToolResult(
                        error=f"Todo item {i} missing required field 'activeForm'"
                    )

                # Validate status
                valid_statuses = ["pending", "in_progress", "completed"]
                if todo["status"] not in valid_statuses:
                    return ToolResult(
                        error=f"Todo item {i} has invalid status '{todo['status']}'. "
                        f"Must be one of: {', '.join(valid_statuses)}"
                    )

                # Validate content is not empty
                if not todo["content"].strip():
                    return ToolResult(
                        error=f"Todo item {i} has empty content"
                    )

                # Validate activeForm is not empty
                if not todo["activeForm"].strip():
                    return ToolResult(
                        error=f"Todo item {i} has empty activeForm"
                    )

            # Check that only one task is in_progress
            in_progress_count = sum(1 for t in todos if t["status"] == "in_progress")
            if in_progress_count > 1:
                return ToolResult(
                    error=f"Only ONE task can be in_progress at a time. Found {in_progress_count} tasks marked as in_progress."
                )

            # Save the todos
            TodoReadTool.set_todos(todos)

            # Build success message
            pending_count = sum(1 for t in todos if t["status"] == "pending")
            in_progress_count = sum(1 for t in todos if t["status"] == "in_progress")
            completed_count = sum(1 for t in todos if t["status"] == "completed")

            output = f"Todo list updated successfully.\n"
            output += f"Total: {len(todos)} tasks\n"
            output += f"  - Pending: {pending_count}\n"
            output += f"  - In Progress: {in_progress_count}\n"
            output += f"  - Completed: {completed_count}"

            # Add current task info
            if in_progress_count == 1:
                current_task = next(t for t in todos if t["status"] == "in_progress")
                output += f"\n\nCurrently working on: {current_task['activeForm']}"

            return ToolResult(output=output)

        except Exception as e:
            return ToolResult(
                error=f"Error updating todo list: {type(e).__name__}: {str(e)}"
            )
