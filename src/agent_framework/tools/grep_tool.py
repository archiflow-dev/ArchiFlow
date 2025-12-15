"""Grep tool for agents - search file contents using regex patterns."""
import os
import re
from typing import Dict, Optional, List
from fnmatch import fnmatch
from pathlib import Path
from .tool_base import BaseTool, ToolResult


class GrepTool(BaseTool):
    """Tool for searching file contents using regular expressions.

    Searches files in a directory for content matching a regex pattern.
    Results are sorted by file modification time (most recent first).
    """

    name: str = "grep"
    description: str = "Searches file contents using regular expressions. Returns file paths containing matches, sorted by modification time. Use for finding files with specific content patterns."

    parameters: Dict = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "The regular expression pattern to search for in file contents"
            },
            "path": {
                "type": "string",
                "description": "The directory to search in. Defaults to current working directory."
            },
            "include": {
                "type": "string",
                "description": "File pattern to include in search (e.g. '*.js', '*.{ts,tsx}'). Supports glob patterns."
            }
        },
        "required": ["pattern"]
    }

    def _expand_braces(self, pattern: str) -> List[str]:
        """Expand brace patterns like '*.{ts,tsx}' into multiple patterns.

        Args:
            pattern: Pattern that may contain braces

        Returns:
            List of expanded patterns
        """
        if '{' not in pattern or '}' not in pattern:
            return [pattern]

        # Find the brace expression
        start = pattern.find('{')
        end = pattern.find('}')

        if start == -1 or end == -1 or start > end:
            return [pattern]

        # Extract parts
        prefix = pattern[:start]
        options = pattern[start+1:end].split(',')
        suffix = pattern[end+1:]

        # Generate all combinations
        results = []
        for option in options:
            results.append(f"{prefix}{option.strip()}{suffix}")

        return results

    def _matches_include_pattern(self, filename: str, include_pattern: str) -> bool:
        """Check if filename matches the include pattern.

        Args:
            filename: Name of file to check
            include_pattern: Pattern to match against (may contain braces)

        Returns:
            True if filename matches any expanded pattern
        """
        patterns = self._expand_braces(include_pattern)
        return any(fnmatch(filename, pattern) for pattern in patterns)

    def _should_skip_file(self, file_path: str) -> bool:
        """Check if file should be skipped (binary, hidden, etc.).

        Args:
            file_path: Path to file

        Returns:
            True if file should be skipped
        """
        # Skip hidden files
        if os.path.basename(file_path).startswith('.'):
            return True

        # Skip common binary extensions
        binary_extensions = {
            '.pyc', '.pyo', '.so', '.dll', '.dylib', '.exe',
            '.bin', '.dat', '.db', '.sqlite', '.jpg', '.jpeg',
            '.png', '.gif', '.bmp', '.ico', '.pdf', '.zip',
            '.tar', '.gz', '.rar', '.7z', '.mp3', '.mp4',
            '.avi', '.mov', '.wav', '.class', '.jar'
        }

        ext = os.path.splitext(file_path)[1].lower()
        return ext in binary_extensions

    def _search_file(self, file_path: str, regex_pattern: re.Pattern) -> bool:
        """Search a file for the regex pattern.

        Args:
            file_path: Path to file to search
            regex_pattern: Compiled regex pattern

        Returns:
            True if pattern found in file
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    if regex_pattern.search(line):
                        return True
            return False
        except Exception:
            # Skip files that can't be read
            return False

    async def execute(
        self,
        pattern: str,
        path: Optional[str] = None,
        include: Optional[str] = None
    ) -> ToolResult:
        """Search file contents for a regex pattern.

        Args:
            pattern: Regular expression pattern to search for
            path: Directory to search in (defaults to current directory)
            include: File pattern to include (e.g., '*.py', '*.{ts,tsx}')

        Returns:
            ToolResult with matching file paths or error
        """
        try:
            # Validate and compile regex pattern
            if not pattern:
                return ToolResult(error="Pattern cannot be empty")

            try:
                regex_pattern = re.compile(pattern)
            except re.error as e:
                return ToolResult(error=f"Invalid regex pattern: {str(e)}")

            # Determine search path
            if path is None:
                search_path = os.getcwd()
            else:
                search_path = os.path.normpath(path)

                # Validate path exists
                if not os.path.exists(search_path):
                    return ToolResult(error=f"Path does not exist: {search_path}")

                # If path is a file, search only that file
                if os.path.isfile(search_path):
                    if self._should_skip_file(search_path):
                        return ToolResult(
                            output=f"No matches found for pattern: {pattern}",
                            system="File appears to be binary or unsupported"
                        )

                    if include and not self._matches_include_pattern(
                        os.path.basename(search_path), include
                    ):
                        return ToolResult(
                            output=f"No matches found for pattern: {pattern}",
                            system="File does not match include pattern"
                        )

                    if self._search_file(search_path, regex_pattern):
                        return ToolResult(
                            output=f"Match found in: {search_path}"
                        )
                    else:
                        return ToolResult(
                            output=f"No matches found for pattern: {pattern}"
                        )

            # Search directory
            matching_files: List[tuple[str, float]] = []
            files_searched = 0

            for root, dirs, files in os.walk(search_path):
                # Skip hidden directories
                dirs[:] = [d for d in dirs if not d.startswith('.')]

                for filename in files:
                    file_path = os.path.join(root, filename)

                    # Skip if doesn't match include pattern
                    if include and not self._matches_include_pattern(filename, include):
                        continue

                    # Skip binary/hidden files
                    if self._should_skip_file(file_path):
                        continue

                    files_searched += 1

                    # Search file
                    if self._search_file(file_path, regex_pattern):
                        # Get modification time for sorting
                        try:
                            mtime = os.path.getmtime(file_path)
                            matching_files.append((file_path, mtime))
                        except OSError:
                            # If can't get mtime, add with 0
                            matching_files.append((file_path, 0))

            # Sort by modification time (most recent first)
            matching_files.sort(key=lambda x: x[1], reverse=True)

            # Format output
            if not matching_files:
                output = f"No matches found for pattern: {pattern}\n"
                output += f"Searched {files_searched} file(s)"
                if include:
                    output += f" matching pattern: {include}"
                return ToolResult(output=output)

            output = f"Found {len(matching_files)} file(s) matching pattern: {pattern}\n"
            if include:
                output += f"File filter: {include}\n"
            output += f"Searched {files_searched} file(s)\n"
            output += "\nMatching files (sorted by modification time):\n"

            for file_path, _ in matching_files:
                # Show relative path if within search directory
                try:
                    rel_path = os.path.relpath(file_path, search_path)
                    if not rel_path.startswith('..'):
                        output += f"  {rel_path}\n"
                    else:
                        output += f"  {file_path}\n"
                except ValueError:
                    # On Windows, relpath fails for different drives
                    output += f"  {file_path}\n"

            return ToolResult(output=output.rstrip())

        except Exception as e:
            return ToolResult(
                error=f"Error performing grep: {type(e).__name__}: {str(e)}"
            )
