"""Glob tool for agents - find files using glob patterns."""
import os
import glob as glob_module
from typing import Dict, Optional, List
from .tool_base import BaseTool, ToolResult


class GlobTool(BaseTool):
    """Tool for finding files using glob patterns.

    Supports standard glob patterns including:
    - * matches any characters within a filename
    - ? matches any single character
    - [seq] matches any character in seq
    - [!seq] matches any character not in seq
    - ** matches any files and zero or more directories (recursive)

    Results are sorted by modification time (most recent first).
    """

    name: str = "glob"
    description: str = "Finds files matching glob patterns (e.g., '**/*.py', 'src/**/*.js'). Returns file paths sorted by modification time. Fast pattern matching for any codebase size."

    parameters: Dict = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "The glob pattern to match files against (e.g., '**/*.py', 'src/**/*.ts')"
            },
            "path": {
                "type": "string",
                "description": "The directory to search in. If not specified, the current working directory will be used."
            }
        },
        "required": ["pattern"]
    }

    def _get_file_mtime(self, file_path: str) -> float:
        """Get modification time of a file.

        Args:
            file_path: Path to file

        Returns:
            Modification time as float, or 0 if unable to get
        """
        try:
            return os.path.getmtime(file_path)
        except (OSError, IOError):
            return 0.0

    async def execute(
        self,
        pattern: str,
        path: Optional[str] = None
    ) -> ToolResult:
        """Find files matching a glob pattern.

        Args:
            pattern: Glob pattern to match (e.g., '**/*.py', 'src/**/*.js')
            path: Directory to search in (defaults to current directory)

        Returns:
            ToolResult with matching file paths or error
        """
        try:
            # Validate pattern
            if not pattern:
                return ToolResult(error="Pattern cannot be empty")

            if not isinstance(pattern, str):
                return ToolResult(error="Pattern must be a string")

            # Determine search path
            if path is None:
                search_path = os.getcwd()
            else:
                search_path = os.path.normpath(path)

                # Validate path exists
                if not os.path.exists(search_path):
                    return ToolResult(error=f"Path does not exist: {search_path}")

                # Validate path is a directory
                if not os.path.isdir(search_path):
                    return ToolResult(error=f"Path is not a directory: {search_path}")

            # Save current directory and change to search path
            original_cwd = os.getcwd()
            try:
                os.chdir(search_path)

                # Perform glob search
                # recursive=True enables ** pattern
                matches = glob_module.glob(pattern, recursive=True)

                # Filter out directories, keep only files
                file_matches = [m for m in matches if os.path.isfile(m)]

                # Get modification times and sort
                files_with_mtime: List[tuple[str, float]] = []
                for file_path in file_matches:
                    # Get absolute path for mtime
                    abs_path = os.path.abspath(file_path)
                    mtime = self._get_file_mtime(abs_path)
                    files_with_mtime.append((file_path, mtime))

                # Sort by modification time (most recent first)
                files_with_mtime.sort(key=lambda x: x[1], reverse=True)

                # Extract just the paths
                sorted_files = [f[0] for f in files_with_mtime]

            finally:
                # Always restore original directory
                os.chdir(original_cwd)

            # Format output
            if not sorted_files:
                return ToolResult(
                    output=f"No files found matching pattern: {pattern}"
                )

            # Build output message
            output = f"Found {len(sorted_files)} file(s) matching pattern: {pattern}\n"

            if path:
                output += f"Search path: {search_path}\n"

            output += "\nMatching files (sorted by modification time):\n"

            for file_path in sorted_files:
                # Normalize path separators for display
                display_path = file_path.replace(os.sep, '/')
                output += f"  {display_path}\n"

            return ToolResult(output=output.rstrip())

        except Exception as e:
            return ToolResult(
                error=f"Error performing glob: {type(e).__name__}: {str(e)}"
            )
