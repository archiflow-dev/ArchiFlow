"""File editing tool for agents."""
import os
from typing import Dict, Optional
from .tool_base import BaseTool, ToolResult


class EditTool(BaseTool):
    """Tool for performing exact string replacements in files.

    This tool allows agents to edit files by replacing exact string matches.
    It requires that the file has been read before editing and ensures
    that replacements are unambiguous unless replace_all is specified.
    """

    name: str = "edit"
    description: str = "Performs exact string replacements in files. Supports both absolute and relative paths. The old_string must exist in the file and be unique (unless replace_all is True). Preserves exact indentation and formatting."

    parameters: Dict = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "The path to the file to modify (absolute or relative to project directory)"
            },
            "old_string": {
                "type": "string",
                "description": "The exact text to replace. Must match exactly including whitespace and indentation."
            },
            "new_string": {
                "type": "string",
                "description": "The text to replace it with (must be different from old_string)"
            },
            "replace_all": {
                "type": "boolean",
                "description": "If True, replace all occurrences of old_string. If False (default), old_string must be unique in the file.",
                "default": False
            }
        },
        "required": ["file_path", "old_string", "new_string"]
    }

    async def execute(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False
    ) -> ToolResult:
        """Perform exact string replacement in a file.

        Args:
            file_path: Path to the file (absolute or relative to project directory)
            old_string: The exact text to replace
            new_string: The replacement text
            replace_all: If True, replace all occurrences; if False, require uniqueness

        Returns:
            ToolResult with success message or error
        """
        try:
            # NEW: Resolve path first
            file_path = self.resolve_path(file_path)

            # Normalize path for cross-platform compatibility
            file_path = os.path.normpath(file_path)

            # Check if file exists
            if not os.path.exists(file_path):
                return ToolResult(
                    error=f"File does not exist: {file_path}"
                )

            # Check if path is a file (not a directory)
            if not os.path.isfile(file_path):
                return ToolResult(
                    error=f"Path is not a file: {file_path}"
                )

            # Validate that old_string and new_string are different
            if old_string == new_string:
                return ToolResult(
                    error="old_string and new_string must be different"
                )

            # Read the file contents
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    original_content = f.read()
            except UnicodeDecodeError:
                return ToolResult(
                    error=f"File appears to be binary or not UTF-8 encoded: {file_path}"
                )

            # Check if old_string exists in the file
            if old_string not in original_content:
                return ToolResult(
                    error=f"old_string not found in file. The exact string must match including all whitespace and indentation."
                )

            # Count occurrences
            occurrence_count = original_content.count(old_string)

            # If not replace_all, ensure old_string is unique
            if not replace_all and occurrence_count > 1:
                return ToolResult(
                    error=f"old_string appears {occurrence_count} times in the file. "
                    f"Either provide a larger string with more surrounding context to make it unique, "
                    f"or set replace_all=True to replace all occurrences."
                )

            # Perform the replacement
            if replace_all:
                new_content = original_content.replace(old_string, new_string)
                replacements_made = occurrence_count
            else:
                # Replace only the first occurrence (which we know is the only one)
                new_content = original_content.replace(old_string, new_string, 1)
                replacements_made = 1

            # Write the modified content back to the file
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
            except PermissionError:
                return ToolResult(
                    error=f"Permission denied: Cannot write to {file_path}"
                )

            # Calculate change statistics
            original_lines = original_content.count('\n') + 1
            new_lines = new_content.count('\n') + 1
            lines_changed = abs(new_lines - original_lines)

            # Create success message
            success_msg = f"Successfully edited {file_path}\n"
            success_msg += f"Replaced {replacements_made} occurrence(s) of old_string with new_string"

            if lines_changed > 0:
                action = "added" if new_lines > original_lines else "removed"
                success_msg += f"\n{lines_changed} line(s) {action}"

            return ToolResult(output=success_msg)

        except PermissionError:
            return ToolResult(
                error=f"Permission denied: {file_path}"
            )
        except Exception as e:
            return ToolResult(
                error=f"Error editing file: {type(e).__name__}: {str(e)}"
            )


class SafeEditTool(EditTool):
    """A restricted version of EditTool that creates backups before editing.

    This version automatically creates a backup file with a .bak extension
    before making any changes, providing a safety net for edits.
    """

    name: str = "safe_edit"
    description: str = "Performs exact string replacements in files with automatic backup creation. Creates a .bak file before editing."

    async def execute(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False
    ) -> ToolResult:
        """Perform exact string replacement with automatic backup.

        Args:
            file_path: Absolute path to the file to modify
            old_string: The exact text to replace
            new_string: The replacement text
            replace_all: If True, replace all occurrences; if False, require uniqueness

        Returns:
            ToolResult with success message or error
        """
        try:
            # Normalize path
            file_path = os.path.normpath(file_path)

            # Validate file exists
            if not os.path.exists(file_path):
                return ToolResult(
                    error=f"File does not exist: {file_path}"
                )

            # Create backup
            backup_path = file_path + ".bak"
            try:
                with open(file_path, 'r', encoding='utf-8') as source:
                    content = source.read()
                with open(backup_path, 'w', encoding='utf-8') as backup:
                    backup.write(content)
            except Exception as e:
                return ToolResult(
                    error=f"Failed to create backup: {type(e).__name__}: {str(e)}"
                )

            # Perform the edit using parent class
            result = await super().execute(file_path, old_string, new_string, replace_all)

            # If successful, append backup info to output
            if result.output:
                result = result.replace(
                    output=result.output + f"\nBackup created at: {backup_path}"
                )

            return result

        except Exception as e:
            return ToolResult(
                error=f"Error in safe edit: {type(e).__name__}: {str(e)}"
            )
