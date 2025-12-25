"""
Configuration merge utilities for ArchiFlow hierarchy system.

This module provides deep merge functionality for combining configuration
from multiple levels of the hierarchy (framework, global, project).
"""
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deep merge two dictionaries.

    Nested dictionaries are merged recursively. Lists are replaced
    (not merged) unless you use merge_lists_with_append.

    Args:
        base: The base dictionary
        override: The override dictionary (higher precedence)

    Returns:
        A new dictionary with merged values

    Examples:
        >>> base = {"a": {"x": 1, "y": 2}, "b": 3}
        >>> override = {"a": {"y": 20, "z": 30}, "c": 4}
        >>> deep_merge(base, override)
        {'a': {'x': 1, 'y': 20, 'z': 30}, 'b': 3, 'c': 4}
    """
    result = base.copy()

    for key, value in override.items():
        if key in result:
            if isinstance(result[key], dict) and isinstance(value, dict):
                # Recursively merge nested dictionaries
                result[key] = deep_merge(result[key], value)
            elif isinstance(result[key], list) and isinstance(value, list):
                # Replace lists (default behavior)
                result[key] = value
            else:
                # Override with new value
                result[key] = value
        else:
            # Add new key
            result[key] = value

    return result


def deep_merge_multiple(configs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Deep merge multiple dictionaries in order.

    Earlier dictionaries have lower precedence, later dictionaries
    have higher precedence.

    Args:
        configs: List of dictionaries to merge

    Returns:
        A new dictionary with all configs merged

    Examples:
        >>> c1 = {"a": {"x": 1}}
        >>> c2 = {"a": {"y": 2}}
        >>> c3 = {"a": {"z": 3}, "b": 4}
        >>> deep_merge_multiple([c1, c2, c3])
        {'a': {'x': 1, 'y': 2, 'z': 3}, 'b': 4}
    """
    if not configs:
        return {}

    result: Dict[str, Any] = {}

    for config in configs:
        result = deep_merge(result, config)

    return result


def merge_with_precedence(
    framework: Optional[Dict[str, Any]] = None,
    global_user: Optional[Dict[str, Any]] = None,
    project: Optional[Dict[str, Any]] = None,
    project_local: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Merge configurations from all hierarchy levels.

    Precedence (highest to lowest):
    1. project_local
    2. project
    3. global_user
    4. framework

    Args:
        framework: Framework default configuration
        global_user: Global user configuration (~/.archiflow/)
        project: Project configuration (./.archiflow/)
        project_local: Project local configuration (gitignored)

    Returns:
        Merged configuration
    """
    configs = []

    # Add in precedence order (lowest first)
    if framework:
        configs.append(framework)
    if global_user:
        configs.append(global_user)
    if project:
        configs.append(project)
    if project_local:
        configs.append(project_local)

    return deep_merge_multiple(configs)


def merge_settings_configs(configs: List[tuple]) -> Dict[str, Any]:
    """
    Merge settings configs with path tracking.

    Args:
        configs: List of (path, data) tuples from loader

    Returns:
        Merged configuration
    """
    dict_configs = [data for _, data in configs]
    return deep_merge_multiple(dict_configs)


def merge_context_files(
    framework_path: Optional[str] = None,
    global_path: Optional[str] = None,
    project_path: Optional[str] = None,
    project_local_path: Optional[str] = None,
    delimiter: str = "\n\n---\n\n"
) -> str:
    """
    Merge context files by concatenating them.

    Args:
        framework_path: Path to framework context file
        global_path: Path to global context file
        project_path: Path to project context file
        project_local_path: Path to project local context file
        delimiter: String to insert between sections

    Returns:
        Concatenated context content
    """
    parts = []

    if framework_path:
        parts.append(("# From: Framework Defaults\n\n" + framework_path).strip())
    if global_path:
        parts.append(("# From: ~/.archiflow/ARCHIFLOW.md\n\n" + global_path).strip())
    if project_path:
        parts.append(("# From: ./.archiflow/ARCHIFLOW.md\n\n" + project_path).strip())
    if project_local_path:
        parts.append(("# From: ./.archiflow/ARCHIFLOW.local.md\n\n" + project_local_path).strip())

    return "\n\n" + delimiter.join(parts) + "\n\n" if parts else ""


def merge_lists_with_append(base: list, override: list) -> list:
    """
    Merge lists by appending override items to base items.

    This is an alternative to the default list replacement behavior.

    Args:
        base: The base list
        override: The override list

    Returns:
        A new list with appended items

    Examples:
        >>> merge_lists_with_append([1, 2], [3, 4])
        [1, 2, 3, 4]
    """
    return base + override


def merge_lists_unique(base: list, override: list) -> list:
    """
    Merge lists, keeping only unique items.

    Preserves order, with base items first, then new items from override.

    Args:
        base: The base list
        override: The override list

    Returns:
        A new list with unique items

    Examples:
        >>> merge_lists_unique([1, 2, 3], [3, 4, 5])
        [1, 2, 3, 4, 5]
    """
    seen = set()
    result = []

    for item in base + override:
        if item not in seen:
            seen.add(item)
            result.append(item)

    return result


def deep_merge_with_list_strategy(
    base: Dict[str, Any],
    override: Dict[str, Any],
    list_merge: str = "replace"
) -> Dict[str, Any]:
    """
    Deep merge with configurable list merge strategy.

    Args:
        base: The base dictionary
        override: The override dictionary
        list_merge: Strategy for merging lists ("replace", "append", "unique")

    Returns:
        A new dictionary with merged values
    """
    result = base.copy()

    for key, value in override.items():
        if key in result:
            if isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = deep_merge_with_list_strategy(
                    result[key], value, list_merge
                )
            elif isinstance(result[key], list) and isinstance(value, list):
                if list_merge == "append":
                    result[key] = merge_lists_with_append(result[key], value)
                elif list_merge == "unique":
                    result[key] = merge_lists_unique(result[key], value)
                else:
                    result[key] = value  # replace (default)
            else:
                result[key] = value
        else:
            result[key] = value

    return result


def get_effective_value(
    configs: List[Dict[str, Any]],
    key_path: str,
    default: Any = None
) -> Any:
    """
    Get the effective value for a nested key across all configs.

    Args:
        configs: List of configuration dicts in precedence order
        key_path: Dot-separated path to the key (e.g., "agent.timeout")
        default: Default value if key not found

    Returns:
        The effective value, or default if not found

    Examples:
        >>> configs = [{"a": {"x": 1}}, {"a": {"y": 2}}]
        >>> get_effective_value(configs, "a.x")
        1
        >>> get_effective_value(configs, "a.y")
        2
    """
    keys = key_path.split(".")

    for config in reversed(configs):  # Start with highest precedence
        value = config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                value = None
                break

        if value is not None:
            return value

    return default
