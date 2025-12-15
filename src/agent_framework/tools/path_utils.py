"""
Path resolution utilities for agent tools.

Provides consistent path resolution across all tools, supporting both
absolute and relative paths with proper normalization.
"""

import os
from pathlib import Path
from typing import Optional


def resolve_path(
    path: str,
    working_directory: Optional[str] = None,
    strict: bool = False
) -> str:
    """
    Resolve a file path to an absolute normalized path.

    This function handles both absolute and relative paths, resolving
    relative paths against the provided working_directory.

    Args:
        path: The file path to resolve (absolute or relative)
        working_directory: Base directory for resolving relative paths.
                          If None and path is relative, uses current directory.
        strict: If True and working_directory is provided, verify the resolved
               path is within the working_directory tree.

    Returns:
        Absolute, normalized path as a string

    Raises:
        ValueError: If strict=True and resolved path is outside working_directory
        ValueError: If path is empty or contains only whitespace

    Examples:
        >>> resolve_path("/absolute/path")
        '/absolute/path'

        >>> resolve_path("relative/file.py", working_directory="/project")
        '/project/relative/file.py'

        >>> resolve_path("../outside", working_directory="/project", strict=True)
        ValueError: Resolved path is outside working directory
    """
    # Validate input
    if not path or not path.strip():
        raise ValueError("Path cannot be empty")

    # Create Path object
    path_obj = Path(path)

    # Handle absolute paths
    if path_obj.is_absolute():
        resolved = path_obj.resolve()
    else:
        # Handle relative paths
        if working_directory:
            base = Path(working_directory).resolve()
            resolved = (base / path_obj).resolve()
        else:
            # No working directory, resolve against current directory
            resolved = path_obj.resolve()

    # Strict mode: verify path is under working_directory
    if strict and working_directory:
        base = Path(working_directory).resolve()
        try:
            # Check if resolved path is relative to base
            resolved.relative_to(base)
        except ValueError:
            raise ValueError(
                f"Resolved path '{resolved}' is outside working directory '{base}'. "
                f"In strict mode, all file operations must be within the project directory."
            )

    return str(resolved)


def is_safe_path(path: str, base_directory: str) -> bool:
    """
    Check if a path is safely within a base directory.

    This is a utility function for tools that want to validate paths
    without raising exceptions.

    Args:
        path: The path to check (will be resolved)
        base_directory: The base directory to check against

    Returns:
        True if the resolved path is within base_directory, False otherwise

    Examples:
        >>> is_safe_path("src/main.py", "/project")
        True

        >>> is_safe_path("../../etc/passwd", "/project")
        False
    """
    try:
        path_obj = Path(path)
        base = Path(base_directory).resolve()

        # If path is relative, resolve it against base_directory
        if not path_obj.is_absolute():
            resolved = (base / path_obj).resolve()
        else:
            resolved = path_obj.resolve()

        # Check if resolved is under base
        resolved.relative_to(base)
        return True
    except (ValueError, OSError):
        return False


def normalize_path(path: str) -> str:
    """
    Normalize a path for cross-platform compatibility.

    Converts separators and resolves . and .. components without
    following symlinks.

    Args:
        path: Path to normalize

    Returns:
        Normalized path string

    Examples:
        >>> normalize_path("src/./utils/../main.py")
        'src/main.py'
    """
    return os.path.normpath(path)
