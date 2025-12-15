"""Sandboxed write tool for CodeReviewAgent.

This tool restricts file writes to the .agent/review/ directory to prevent
path traversal attacks and ensure reviews only write to their designated area.
"""
import os
from pathlib import Path
from typing import Dict, Optional
from pydantic import Field
from .tool_base import BaseTool, ToolResult


class ReviewWriteTool(BaseTool):
    """Sandboxed write tool restricted to .agent/review/ directory.

    Security features:
    - Path traversal protection (ensures resolved path stays within sandbox)
    - Automatic directory creation
    - No read-before-write requirement (reviews create new files)
    """

    name: str = "write_review_file"
    description: str = """Write review files to the .agent/review/ directory.
Use this to write review results in JSON or Markdown format.
Paths should be relative to .agent/review/ (e.g., 'results/latest.json' or 'results/latest.md').
Creates parent directories automatically."""

    parameters: Dict = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path relative to .agent/review/ directory (e.g., 'results/latest.json', 'results/latest.md')"
            },
            "content": {
                "type": "string",
                "description": "The content to write to the file"
            }
        },
        "required": ["file_path", "content"]
    }

    # Pydantic fields - all instance attributes must be declared
    project_directory: Optional[str] = Field(default=None, exclude=True)
    sandbox_dir: Optional[Path] = Field(default=None, exclude=True)

    def __init__(self, project_directory: str = None, **kwargs):
        """Initialize the review write tool.

        Args:
            project_directory: Root project directory containing .agent/review/
            **kwargs: Additional arguments passed to BaseTool
        """
        # Set project_directory before calling super().__init__
        if project_directory is None:
            project_directory = os.getcwd()

        # Calculate sandbox_dir
        sandbox_dir = Path(project_directory) / ".agent" / "review"

        # Call super().__init__ with all field values
        super().__init__(
            project_directory=project_directory,
            sandbox_dir=sandbox_dir,
            **kwargs
        )

        # Ensure sandbox directory exists
        self.sandbox_dir.mkdir(parents=True, exist_ok=True)

    def _is_safe_path(self, file_path: str) -> tuple[bool, str]:
        """Check if path is within sandbox directory (prevents path traversal).

        Args:
            file_path: The file path to check

        Returns:
            Tuple of (is_safe, resolved_absolute_path)
        """
        try:
            # Resolve the full path
            if os.path.isabs(file_path):
                # If absolute, check it's within sandbox
                resolved = Path(file_path).resolve()
            else:
                # If relative, resolve relative to sandbox
                resolved = (self.sandbox_dir / file_path).resolve()

            # Check if resolved path is within sandbox (prevents ../ attacks)
            try:
                resolved.relative_to(self.sandbox_dir)
                return True, str(resolved)
            except ValueError:
                # Path is outside sandbox
                return False, str(resolved)

        except Exception as e:
            return False, f"Error resolving path: {e}"

    async def execute(
        self,
        file_path: str,
        content: str
    ) -> ToolResult:
        """Write content to a file within the .agent/review/ sandbox.

        Args:
            file_path: Path relative to .agent/review/ or absolute within sandbox
            content: The content to write to the file

        Returns:
            ToolResult with success message or error
        """
        try:
            # Security check: validate path is within sandbox
            is_safe, resolved_path = self._is_safe_path(file_path)

            if not is_safe:
                return ToolResult(
                    error=f"Security error: Path '{file_path}' is outside .agent/review/ directory. "
                    f"Attempted to access: {resolved_path}"
                )

            resolved_path_obj = Path(resolved_path)

            # Check if path is a directory
            if resolved_path_obj.exists() and resolved_path_obj.is_dir():
                return ToolResult(
                    error=f"Path is a directory, not a file: {file_path}"
                )

            # Create parent directory if needed
            parent_dir = resolved_path_obj.parent
            if not parent_dir.exists():
                try:
                    parent_dir.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    return ToolResult(
                        error=f"Failed to create parent directory: {type(e).__name__}: {str(e)}"
                    )

            # Write the file
            file_exists = resolved_path_obj.exists()

            try:
                with open(resolved_path_obj, 'w', encoding='utf-8') as f:
                    f.write(content)
            except PermissionError:
                return ToolResult(
                    error=f"Permission denied: Cannot write to {file_path}"
                )

            # Calculate statistics
            lines = content.count('\n') + (1 if content and not content.endswith('\n') else 0)
            size = len(content.encode('utf-8'))

            # Relative path for display (relative to sandbox)
            try:
                display_path = resolved_path_obj.relative_to(self.sandbox_dir)
            except ValueError:
                display_path = resolved_path_obj

            # Create success message
            action = "Overwrote" if file_exists else "Created"
            success_msg = f"{action} review file: .agent/review/{display_path}\n"
            success_msg += f"Lines: {lines}\n"
            success_msg += f"Size: {size} bytes"

            return ToolResult(output=success_msg)

        except Exception as e:
            return ToolResult(
                error=f"Error writing review file: {type(e).__name__}: {str(e)}"
            )
