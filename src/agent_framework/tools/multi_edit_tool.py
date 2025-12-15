"""Multi-edit tool for agents - perform multiple edits in one operation."""
import os
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from .tool_base import BaseTool, ToolResult


class EditOperation(BaseModel):
    """Represents a single edit operation."""
    old_string: str = Field(description="The text to replace")
    new_string: str = Field(description="The text to replace it with")
    replace_all: bool = Field(default=False, description="Replace all occurrences")


class MultiEditTool(BaseTool):
    """Tool for performing multiple edits on a single file atomically.

    This tool allows multiple find-and-replace operations on a file in a single
    atomic operation. All edits must succeed or none are applied. Edits are
    applied sequentially, with each edit operating on the result of the previous one.
    """

    name: str = "multi_edit"
    description: str = "Performs multiple edits on a single file atomically. All edits are applied sequentially and either all succeed or none are applied. Prefer this over Edit when making multiple changes to one file."

    parameters: Dict = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "The absolute path to the file to modify (must be absolute, not relative)"
            },
            "edits": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "old_string": {
                            "type": "string",
                            "description": "The text to replace (must match exactly including whitespace)"
                        },
                        "new_string": {
                            "type": "string",
                            "description": "The text to replace it with"
                        },
                        "replace_all": {
                            "type": "boolean",
                            "description": "If True, replace all occurrences; if False (default), require uniqueness",
                            "default": False
                        }
                    },
                    "required": ["old_string", "new_string"]
                },
                "description": "Array of edit operations to perform sequentially",
                "minItems": 1
            }
        },
        "required": ["file_path", "edits"]
    }

    def _validate_edit(
        self,
        content: str,
        old_string: str,
        new_string: str,
        replace_all: bool,
        edit_index: int
    ) -> Optional[str]:
        """Validate a single edit operation.

        Args:
            content: Current file content
            old_string: Text to replace
            new_string: Replacement text
            replace_all: Whether to replace all occurrences
            edit_index: Index of this edit (for error messages)

        Returns:
            Error message if invalid, None if valid
        """
        # Check if old_string and new_string are different
        if old_string == new_string:
            return f"Edit {edit_index + 1}: old_string and new_string must be different"

        # Check if old_string exists in content
        if old_string not in content:
            return f"Edit {edit_index + 1}: old_string not found in file (or in result of previous edits)"

        # Check uniqueness if not replace_all
        if not replace_all:
            occurrence_count = content.count(old_string)
            if occurrence_count > 1:
                return (
                    f"Edit {edit_index + 1}: old_string appears {occurrence_count} times. "
                    f"Either provide more context to make it unique or set replace_all=True"
                )

        return None

    def _apply_edit(
        self,
        content: str,
        old_string: str,
        new_string: str,
        replace_all: bool
    ) -> str:
        """Apply a single edit to the content.

        Args:
            content: Current content
            old_string: Text to replace
            new_string: Replacement text
            replace_all: Whether to replace all occurrences

        Returns:
            Modified content
        """
        if replace_all:
            return content.replace(old_string, new_string)
        else:
            # Replace only the first occurrence
            return content.replace(old_string, new_string, 1)

    async def execute(
        self,
        file_path: str,
        edits: List[Dict]
    ) -> ToolResult:
        """Perform multiple edits on a file atomically.

        Args:
            file_path: Absolute path to the file to modify
            edits: List of edit operations (dicts with old_string, new_string, replace_all)

        Returns:
            ToolResult with success message or error
        """
        try:
            # Normalize path for cross-platform compatibility
            file_path = os.path.normpath(file_path)

            # Validate file path is absolute
            if not os.path.isabs(file_path):
                return ToolResult(
                    error=f"File path must be absolute, not relative: {file_path}"
                )

            # Validate we have at least one edit
            if not edits or len(edits) == 0:
                return ToolResult(
                    error="At least one edit operation must be provided"
                )

            # Parse edit operations
            edit_operations = []
            for i, edit_dict in enumerate(edits):
                try:
                    edit_op = EditOperation(**edit_dict)
                    edit_operations.append(edit_op)
                except Exception as e:
                    return ToolResult(
                        error=f"Invalid edit operation {i + 1}: {str(e)}"
                    )

            # Check if this is a file creation (first edit has empty old_string)
            is_creation = (len(edit_operations) > 0 and
                          edit_operations[0].old_string == "" and
                          not os.path.exists(file_path))

            if is_creation:
                # Creating a new file
                # First edit should have empty old_string
                if edit_operations[0].old_string != "":
                    return ToolResult(
                        error="For file creation, the first edit must have empty old_string"
                    )

                # Create parent directory if needed
                parent_dir = os.path.dirname(file_path)
                if parent_dir and not os.path.exists(parent_dir):
                    try:
                        os.makedirs(parent_dir, exist_ok=True)
                    except Exception as e:
                        return ToolResult(
                            error=f"Failed to create parent directory: {str(e)}"
                        )

                # Start with empty content for creation
                original_content = ""
                current_content = edit_operations[0].new_string

                # Apply remaining edits starting from index 1
                edit_start_index = 1
            else:
                # Editing existing file
                # Check if file exists
                if not os.path.exists(file_path):
                    return ToolResult(
                        error=f"File does not exist: {file_path}"
                    )

                # Check if path is a file
                if not os.path.isfile(file_path):
                    return ToolResult(
                        error=f"Path is not a file: {file_path}"
                    )

                # Check if file was read first (for existing files)
                try:
                    from .write_tool import WriteTool
                    if not WriteTool.was_file_read(file_path):
                        return ToolResult(
                            error=f"File must be read first before editing. Use Read tool on {file_path}"
                        )
                except ImportError:
                    pass  # WriteTool not available

                # Read original content
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        original_content = f.read()
                except UnicodeDecodeError:
                    return ToolResult(
                        error=f"File appears to be binary or not UTF-8 encoded: {file_path}"
                    )

                current_content = original_content
                edit_start_index = 0

            # Validate all edits before applying any
            for i in range(edit_start_index, len(edit_operations)):
                edit_op = edit_operations[i]
                error = self._validate_edit(
                    current_content,
                    edit_op.old_string,
                    edit_op.new_string,
                    edit_op.replace_all,
                    i
                )

                if error:
                    return ToolResult(error=error)

                # Simulate the edit for next validation
                current_content = self._apply_edit(
                    current_content,
                    edit_op.old_string,
                    edit_op.new_string,
                    edit_op.replace_all
                )

            # All edits validated - now apply them for real
            # Reset to original/starting content
            if is_creation:
                final_content = edit_operations[0].new_string
                edits_applied = 1
            else:
                final_content = original_content
                edits_applied = 0

            # Apply all edits
            for i in range(edit_start_index, len(edit_operations)):
                edit_op = edit_operations[i]
                final_content = self._apply_edit(
                    final_content,
                    edit_op.old_string,
                    edit_op.new_string,
                    edit_op.replace_all
                )
                edits_applied += 1

            # Write the final content
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(final_content)
            except PermissionError:
                return ToolResult(
                    error=f"Permission denied: Cannot write to {file_path}"
                )

            # Calculate statistics
            original_lines = original_content.count('\n') + 1 if original_content else 0
            final_lines = final_content.count('\n') + 1
            lines_changed = abs(final_lines - original_lines)

            # Create success message
            if is_creation:
                action = "Created"
            else:
                action = "Edited"

            success_msg = f"{action} file: {file_path}\n"
            success_msg += f"Applied {edits_applied} edit(s) successfully\n"

            if lines_changed > 0:
                change_type = "added" if final_lines > original_lines else "removed"
                success_msg += f"{lines_changed} line(s) {change_type}"

            # Mark file as read for future write operations
            try:
                from .write_tool import WriteTool
                WriteTool.mark_as_read(file_path)
            except ImportError:
                pass

            return ToolResult(output=success_msg)

        except Exception as e:
            return ToolResult(
                error=f"Error performing multi-edit: {type(e).__name__}: {str(e)}"
            )
