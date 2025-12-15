"""File writing tool for agents."""
import os
from typing import Dict, Set, ClassVar
from .tool_base import BaseTool, ToolResult


class WriteTool(BaseTool):
    """Tool for writing files to the local filesystem.

    This tool writes content to files, creating new files or overwriting existing ones.
    For safety, it requires that existing files be read first before overwriting.
    """

    name: str = "write"
    description: str = "Writes a file to the local filesystem. Supports both absolute and relative paths. Creates new files or overwrites existing ones. For existing files, you must use the Read tool first."

    parameters: Dict = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "The path to the file to write (absolute or relative to project directory)"
            },
            "content": {
                "type": "string",
                "description": "The content to write to the file"
            }
        },
        "required": ["file_path", "content"]
    }

    # Class-level tracking of read files to enforce read-before-write policy
    _read_files: ClassVar[Set[str]] = set()

    @classmethod
    def mark_as_read(cls, file_path: str) -> None:
        """Mark a file as having been read.

        This should be called by the ReadTool when a file is successfully read.

        Args:
            file_path: The absolute path to the file that was read
        """
        normalized_path = os.path.normpath(os.path.abspath(file_path))
        cls._read_files.add(normalized_path)

    @classmethod
    def clear_read_history(cls) -> None:
        """Clear the read file history.

        This can be used to reset the tracking between sessions or tests.
        """
        cls._read_files.clear()

    @classmethod
    def was_file_read(cls, file_path: str) -> bool:
        """Check if a file was previously read.

        Args:
            file_path: The absolute path to check

        Returns:
            True if the file was marked as read, False otherwise
        """
        normalized_path = os.path.normpath(os.path.abspath(file_path))
        return normalized_path in cls._read_files

    async def execute(
        self,
        file_path: str,
        content: str
    ) -> ToolResult:
        """Write content to a file.

        Args:
            file_path: Path to the file (absolute or relative to project directory)
            content: The content to write to the file

        Returns:
            ToolResult with success message or error
        """
        try:
            # NEW: Resolve path first
            file_path = self.resolve_path(file_path)

            # Normalize path for cross-platform compatibility
            file_path = os.path.normpath(file_path)

            # Check if this is an existing file
            file_exists = os.path.exists(file_path)

            if file_exists:
                # Check if path is a directory
                if os.path.isdir(file_path):
                    return ToolResult(
                        error=f"Path is a directory, not a file: {file_path}"
                    )

                # Check if file was read first
                if not self.was_file_read(file_path):
                    return ToolResult(
                        error=f"Cannot overwrite existing file without reading it first. "
                        f"Use the Read tool to read {file_path} before writing to it."
                    )

            # Create parent directory if it doesn't exist
            parent_dir = os.path.dirname(file_path)
            if parent_dir and not os.path.exists(parent_dir):
                try:
                    os.makedirs(parent_dir, exist_ok=True)
                except Exception as e:
                    return ToolResult(
                        error=f"Failed to create parent directory: {type(e).__name__}: {str(e)}"
                    )

            # Check for documentation files and warn (but don't block)
            file_ext = os.path.splitext(file_path)[1].lower()
            is_readme = os.path.basename(file_path).upper().startswith('README')
            is_doc_file = file_ext in ['.md', '.markdown', '.rst', '.txt'] or is_readme

            # Write the content to the file
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
            except PermissionError:
                return ToolResult(
                    error=f"Permission denied: Cannot write to {file_path}"
                )

            # Calculate file statistics
            lines = content.count('\n') + (1 if content and not content.endswith('\n') else 0)
            size = len(content.encode('utf-8'))

            # Create success message
            action = "Overwrote" if file_exists else "Created"
            success_msg = f"{action} file: {file_path}\n"
            success_msg += f"Lines: {lines}\n"
            success_msg += f"Size: {size} bytes"

            # Add system warning for documentation files
            system_msg = None
            if is_doc_file and not file_exists:
                system_msg = (
                    "Warning: Created a documentation file. "
                    "Prefer editing existing files and only create documentation when explicitly requested."
                )

            return ToolResult(output=success_msg, system=system_msg)

        except Exception as e:
            return ToolResult(
                error=f"Error writing file: {type(e).__name__}: {str(e)}"
            )


class SafeWriteTool(WriteTool):
    """A restricted version of WriteTool that never overwrites existing files.

    This version is safer as it only creates new files and will error
    if you attempt to write to an existing file.
    """

    name: str = "safe_write"
    description: str = "Writes a new file to the local filesystem. Will error if the file already exists. Use this to safely create new files without risk of overwriting."

    async def execute(
        self,
        file_path: str,
        content: str
    ) -> ToolResult:
        """Write content to a new file only.

        Args:
            file_path: Absolute path to the file to write
            content: The content to write to the file

        Returns:
            ToolResult with success message or error
        """
        try:
            # Normalize path
            file_path = os.path.normpath(file_path)

            # Validate file path is absolute
            if not os.path.isabs(file_path):
                return ToolResult(
                    error=f"File path must be absolute, not relative: {file_path}"
                )

            # Check if file already exists
            if os.path.exists(file_path):
                return ToolResult(
                    error=f"File already exists: {file_path}. "
                    f"Use EditTool to modify existing files or WriteTool to overwrite."
                )

            # Use parent class logic for creating new files
            # Temporarily mark as "read" to bypass the check since we know it's new
            self.mark_as_read(file_path)
            result = await super().execute(file_path, content)

            return result

        except Exception as e:
            return ToolResult(
                error=f"Error writing file: {type(e).__name__}: {str(e)}"
            )
