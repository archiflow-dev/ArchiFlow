"""File reading tool for agents."""
import os
from typing import Dict, Optional
from .tool_base import BaseTool, ToolResult


class ReadTool(BaseTool):
    """Tool for reading files from the local filesystem.

    This tool reads files and returns their contents with line numbers,
    similar to 'cat -n' command. Supports reading partial files with
    offset and limit parameters for large files.
    """

    name: str = "read"
    description: str = "Reads a file from the local filesystem. Supports both absolute paths and relative paths (resolved against project directory). Returns file contents with line numbers in cat -n format. Supports optional offset and limit for reading large files in chunks."

    parameters: Dict = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "The path to the file to read (absolute or relative to project directory)"
            },
            "offset": {
                "type": "integer",
                "description": "The line number to start reading from (1-indexed). Only provide if the file is too large to read at once.",
                "minimum": 1
            },
            "limit": {
                "type": "integer",
                "description": "The number of lines to read. Only provide if the file is too large to read at once. Defaults to 2000.",
                "minimum": 1
            }
        },
        "required": ["file_path"]
    }

    async def execute(
        self,
        file_path: str,
        offset: Optional[int] = None,
        limit: Optional[int] = None
    ) -> ToolResult:
        """Read a file and return its contents with line numbers.

        Args:
            file_path: Path to the file (absolute or relative to project directory)
            offset: Starting line number (1-indexed, optional)
            limit: Number of lines to read (default 2000)

        Returns:
            ToolResult with file contents in cat -n format or error
        """
        try:
            # NEW: Resolve path (handles both absolute and relative)
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

            # Set default limit
            if limit is None:
                limit = 2000

            # Set default offset
            if offset is None:
                offset = 1

            # Validate offset
            if offset < 1:
                return ToolResult(
                    error=f"Offset must be >= 1, got: {offset}"
                )

            # Read file
            lines = []
            line_count = 0

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    # Skip lines until we reach offset
                    for _ in range(offset - 1):
                        next(f, None)
                        line_count += 1

                    # Read lines up to limit
                    for i, line in enumerate(f):
                        if i >= limit:
                            break

                        # Remove trailing newline for consistent formatting
                        line = line.rstrip('\n')

                        # Truncate long lines (>2000 chars)
                        if len(line) > 2000:
                            line = line[:2000] + "... (truncated)"

                        # Format with line number (cat -n style with arrow)
                        line_num = offset + i
                        lines.append(f"{line_num:>6}→{line}")
                        line_count += 1

            except UnicodeDecodeError:
                # Try reading as binary if UTF-8 fails
                return ToolResult(
                    error=f"File appears to be binary or not UTF-8 encoded: {file_path}"
                )

            # Handle empty file
            if not lines:
                # Check if file is truly empty or we just read past the end
                with open(file_path, 'r', encoding='utf-8') as f:
                    total_lines = sum(1 for _ in f)

                # Mark file as read for WriteTool tracking
                try:
                    from .write_tool import WriteTool
                    WriteTool.mark_as_read(file_path)
                except ImportError:
                    pass

                if total_lines == 0:
                    return ToolResult(
                        output="(empty file)",
                        system="Warning: File exists but has empty contents"
                    )
                elif offset > total_lines:
                    return ToolResult(
                        error=f"Offset {offset} is beyond end of file (file has {total_lines} lines)"
                    )
                else:
                    return ToolResult(output="(no lines in this range)")

            # Join lines and return
            output = "\n".join(lines)

            # Add metadata about what was read
            metadata = f"\n\nRead {len(lines)} line(s) from {file_path}"
            if offset > 1 or limit != 2000:
                metadata += f" (lines {offset}-{offset + len(lines) - 1})"

            # Mark file as read for WriteTool tracking (lazy import to avoid circular dependency)
            try:
                from .write_tool import WriteTool
                WriteTool.mark_as_read(file_path)
            except ImportError:
                pass  # WriteTool not available yet

            return ToolResult(output=output + metadata)

        except PermissionError:
            return ToolResult(
                error=f"Permission denied: {file_path}"
            )
        except Exception as e:
            return ToolResult(
                error=f"Error reading file: {type(e).__name__}: {str(e)}"
            )
