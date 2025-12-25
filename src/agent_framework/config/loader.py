"""
Configuration file loader for ArchiFlow hierarchy system.

This module provides utilities for loading configuration files
(JSON and Markdown) from the hierarchy.
"""
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ConfigLoadError(Exception):
    """Raised when configuration loading fails."""

    def __init__(self, path: Path, reason: str):
        self.path = path
        self.reason = reason
        super().__init__(f"Failed to load {path}: {reason}")


def load_json_file(path: Path) -> Dict[str, Any]:
    """
    Load a JSON configuration file.

    Args:
        path: Path to the JSON file

    Returns:
        Parsed JSON as a dictionary

    Raises:
        ConfigLoadError: If the file cannot be loaded
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            raise ConfigLoadError(path, f"Expected object, got {type(data).__name__}")

        logger.debug(f"Loaded JSON config: {path}")
        return data

    except json.JSONDecodeError as e:
        raise ConfigLoadError(path, f"Invalid JSON: {e}")
    except Exception as e:
        raise ConfigLoadError(path, str(e))


def load_json_with_defaults(
    path: Path,
    defaults: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Load a JSON file, falling back to defaults if the file doesn't exist.

    Args:
        path: Path to the JSON file
        defaults: Default values to use if file doesn't exist

    Returns:
        Parsed JSON or defaults
    """
    if not path.exists():
        logger.debug(f"Config file not found, using defaults: {path}")
        return defaults or {}

    return load_json_file(path)


def load_markdown_file(path: Path) -> str:
    """
    Load a Markdown file.

    Args:
        path: Path to the Markdown file

    Returns:
        File contents as a string

    Raises:
        ConfigLoadError: If the file cannot be loaded
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        logger.debug(f"Loaded Markdown file: {path}")
        return content

    except Exception as e:
        raise ConfigLoadError(path, str(e))


def concatenate_markdown_files(paths: List[Path], delimiter: str = "\n\n") -> str:
    """
    Concatenate multiple Markdown files with optional delimiters.

    Args:
        paths: List of file paths to concatenate
        delimiter: String to insert between files

    Returns:
        Concatenated content
    """
    contents = []

    for path in paths:
        try:
            content = load_markdown_file(path)
            contents.append(content)
        except ConfigLoadError as e:
            logger.warning(str(e))
            # Continue with other files

    return delimiter.join(contents)


def load_settings_with_precedence(
    config_type: str = "settings",
    working_dir: Optional[Path] = None,
    include_local: bool = True
) -> Dict[str, Any]:
    """
    Load settings from all hierarchy levels (merged later).

    This returns a list of (path, data) tuples in precedence order.

    Args:
        config_type: Type of config (e.g., "settings", "ARCHIFLOW")
        working_dir: Current working directory
        include_local: Whether to include .local.* files

    Returns:
        List of (path, data) tuples in precedence order
    """
    from .paths import resolve_config_paths

    paths = resolve_config_paths(
        config_type=config_type,
        working_dir=working_dir,
        include_local=include_local
    )

    configs = []

    for path in paths:
        try:
            data = load_json_file(path)
            configs.append((path, data))
        except ConfigLoadError as e:
            logger.warning(f"Skipping config due to error: {e}")

    return configs


def load_context_with_precedence(
    context_file: str = "ARCHIFLOW.md",
    working_dir: Optional[Path] = None,
    include_local: bool = True
) -> List[Path]:
    """
    Load context files in precedence order.

    Args:
        context_file: Name of the context file
        working_dir: Current working directory
        include_local: Whether to include .local.* files

    Returns:
        List of file paths in precedence order
    """
    from .paths import resolve_context_paths

    return resolve_context_paths(
        context_file=context_file,
        working_dir=working_dir,
        include_local=include_local
    )


def parse_frontmatter(content: str) -> tuple[Optional[Dict[str, Any]], str]:
    """
    Parse YAML frontmatter from Markdown content.

    Args:
        content: Full Markdown content with frontmatter

    Returns:
        Tuple of (frontmatter_dict, content_without_frontmatter)

    Examples:
        >>> content = "---\\nkey: value\\n---\\n# Content"
        >>> frontmatter, body = parse_frontmatter(content)
        >>> frontmatter["key"]
        'value'
    """
    if not content.startswith("---"):
        return None, content

    # Find the end of frontmatter
    parts = content.split("---", 2)
    if len(parts) < 3:
        return None, content

    frontmatter_text = parts[1].strip()
    remaining_content = parts[2].strip()

    # Parse simple YAML-like frontmatter
    # For full YAML support, add pyyaml dependency
    frontmatter = {}
    for line in frontmatter_text.split("\n"):
        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()

            # Handle lists
            if value.startswith("[") and value.endswith("]"):
                value = [v.strip() for v in value[1:-1].split(",")]
                frontmatter[key] = value
                continue

            # Handle booleans
            if value.lower() == "true":
                value = True
            elif value.lower() == "false":
                value = False

            # Handle numbers
            elif isinstance(value, str) and value.isdigit():
                value = int(value)
            elif isinstance(value, str) and _is_float(value):
                value = float(value)

            frontmatter[key] = value

    return frontmatter, remaining_content


def _is_float(value: str) -> bool:
    """Check if a string represents a float."""
    try:
        float(value)
        return True
    except ValueError:
        return False


def load_tool_config(
    tool_name: str,
    config_file: str = "config.md",
    working_dir: Optional[Path] = None
) -> Optional[str]:
    """
    Load tool-specific configuration.

    Args:
        tool_name: Name of the tool
        config_file: Name of the config file
        working_dir: Current working directory

    Returns:
        Configuration content, or None if not found
    """
    from .paths import resolve_tool_config_path

    path = resolve_tool_config_path(
        tool_name=tool_name,
        config_file=config_file,
        working_dir=working_dir
    )

    if path:
        return load_markdown_file(path)

    return None
