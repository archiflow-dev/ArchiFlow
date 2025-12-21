"""Directory listing tool for agents."""
import os
from typing import Dict, List, Optional
from fnmatch import fnmatch
from .tool_base import BaseTool, ToolResult


class ListTool(BaseTool):
    """Tool for listing files and directories.

    This tool lists the contents of a directory with optional glob pattern
    filtering. For targeted searches, prefer using Glob or Grep tools.
    """

    name: str = "list"
    description: str = "Lists files and directories in a given path. Returns formatted directory listing. Prefer Glob/Grep tools if you know which directories to search."

    parameters: Dict = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the directory to list (absolute or relative to working directory)"
            },
            "ignore": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional list of glob patterns to ignore (e.g., ['*.pyc', '__pycache__', '.git'])"
            }
        },
        "required": ["path"]
    }

    def _should_ignore(self, name: str, ignore_patterns: Optional[List[str]]) -> bool:
        """Check if a file/directory should be ignored.

        Args:
            name: The file or directory name
            ignore_patterns: List of glob patterns to ignore

        Returns:
            True if the name matches any ignore pattern, False otherwise
        """
        if not ignore_patterns:
            return False

        for pattern in ignore_patterns:
            if fnmatch(name, pattern):
                return True

        return False

    def _format_size(self, size: int) -> str:
        """Format file size in human-readable format.

        Args:
            size: Size in bytes

        Returns:
            Formatted size string
        """
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                if unit == 'B':
                    return f"{size}{unit}"
                return f"{size:.1f}{unit}"
            size /= 1024.0
        return f"{size:.1f}PB"

    def _get_item_info(self, path: str, name: str) -> Dict:
        """Get information about a file or directory.

        Args:
            path: The parent directory path
            name: The item name

        Returns:
            Dictionary with item information
        """
        full_path = os.path.join(path, name)
        try:
            stat = os.stat(full_path)
            is_dir = os.path.isdir(full_path)
            is_link = os.path.islink(full_path)

            return {
                'name': name,
                'type': 'symlink' if is_link else ('directory' if is_dir else 'file'),
                'size': stat.st_size if not is_dir else None,
                'readable': os.access(full_path, os.R_OK),
                'writable': os.access(full_path, os.W_OK),
            }
        except (OSError, PermissionError):
            return {
                'name': name,
                'type': 'unknown',
                'size': None,
                'readable': False,
                'writable': False,
            }

    async def execute(
        self,
        path: str,
        ignore: Optional[List[str]] = None
    ) -> ToolResult:
        """List files and directories in a path.

        Args:
            path: Path to the directory to list (absolute or relative to working directory)
            ignore: Optional list of glob patterns to ignore

        Returns:
            ToolResult with directory listing or error
        """
        try:
            # Resolve path using execution context (handles relative paths)
            path = self.resolve_path(path)

            # Normalize path for cross-platform compatibility
            path = os.path.normpath(path)

            # Check if path exists
            if not os.path.exists(path):
                return ToolResult(
                    error=f"Path does not exist: {path}"
                )

            # Check if path is a directory
            if not os.path.isdir(path):
                return ToolResult(
                    error=f"Path is not a directory: {path}"
                )

            # Check if we have permission to read the directory
            if not os.access(path, os.R_OK):
                return ToolResult(
                    error=f"Permission denied: Cannot read directory {path}"
                )

            # List directory contents
            try:
                entries = os.listdir(path)
            except PermissionError:
                return ToolResult(
                    error=f"Permission denied: Cannot list directory {path}"
                )

            # Filter ignored entries
            filtered_entries = [
                name for name in entries
                if not self._should_ignore(name, ignore)
            ]

            # Get information about each entry
            items = []
            for name in filtered_entries:
                item_info = self._get_item_info(path, name)
                items.append(item_info)

            # Sort: directories first, then files, alphabetically within each group
            items.sort(key=lambda x: (x['type'] != 'directory', x['name'].lower()))

            # Format output
            if not items:
                return ToolResult(
                    output="(empty directory)",
                    system=f"Listed directory: {path}"
                )

            # Build formatted listing
            lines = []
            lines.append(f"Directory: {path}")
            lines.append("=" * 80)

            # Separate directories and files
            directories = [item for item in items if item['type'] == 'directory']
            files = [item for item in items if item['type'] == 'file']
            symlinks = [item for item in items if item['type'] == 'symlink']
            unknown = [item for item in items if item['type'] == 'unknown']

            # List directories
            if directories:
                lines.append(f"\nDirectories ({len(directories)}):")
                lines.append("-" * 80)
                for item in directories:
                    perms = ""
                    if item['readable'] and item['writable']:
                        perms = "rw"
                    elif item['readable']:
                        perms = "r-"
                    elif item['writable']:
                        perms = "-w"
                    else:
                        perms = "--"
                    lines.append(f"  [{perms}] {item['name']}/")

            # List files
            if files:
                lines.append(f"\nFiles ({len(files)}):")
                lines.append("-" * 80)
                for item in files:
                    perms = ""
                    if item['readable'] and item['writable']:
                        perms = "rw"
                    elif item['readable']:
                        perms = "r-"
                    elif item['writable']:
                        perms = "-w"
                    else:
                        perms = "--"

                    size_str = self._format_size(item['size']) if item['size'] is not None else "?"
                    lines.append(f"  [{perms}] {item['name']:50s} {size_str:>10s}")

            # List symlinks
            if symlinks:
                lines.append(f"\nSymbolic Links ({len(symlinks)}):")
                lines.append("-" * 80)
                for item in symlinks:
                    lines.append(f"  [ln] {item['name']} -> (target)")

            # List unknown items
            if unknown:
                lines.append(f"\nOther ({len(unknown)}):")
                lines.append("-" * 80)
                for item in unknown:
                    lines.append(f"  [??] {item['name']}")

            # Add summary
            lines.append("")
            lines.append("=" * 80)
            total_count = len(directories) + len(files) + len(symlinks) + len(unknown)
            lines.append(f"Total: {total_count} items ({len(directories)} directories, {len(files)} files)")

            if ignore:
                ignored_count = len(entries) - len(filtered_entries)
                if ignored_count > 0:
                    lines.append(f"Ignored: {ignored_count} items (matched ignore patterns)")

            output = "\n".join(lines)

            # Add system message if glob/grep would be better
            system_msg = None
            if len(items) > 50:
                system_msg = "Large directory. Consider using Glob tool with patterns or Grep tool for specific searches."

            return ToolResult(output=output, system=system_msg)

        except Exception as e:
            return ToolResult(
                error=f"Error listing directory: {type(e).__name__}: {str(e)}"
            )
