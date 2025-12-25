"""
Path resolution utilities for ArchiFlow configuration hierarchy.

This module provides utilities for resolving configuration file paths
across the hierarchy: framework defaults, global user config, and
project-specific config.
"""
import os
from pathlib import Path
from typing import Optional, List


def get_global_archiflow_dir() -> Path:
    """
    Get the global ArchiFlow directory (~/.archiflow/).

    Returns:
        Path to the global ArchiFlow directory
    """
    return Path.home() / ".archiflow"


def get_project_archiflow_dir(working_dir: Optional[Path] = None) -> Optional[Path]:
    """
    Get the project ArchiFlow directory (./.archiflow/).

    Args:
        working_dir: Current working directory (defaults to os.getcwd())

    Returns:
        Path to project ArchiFlow directory if found, None otherwise
    """
    if working_dir is None:
        working_dir = Path(os.getcwd())

    # Check for .archiflow in current directory
    archiflow_dir = working_dir / ".archiflow"
    if archiflow_dir.is_dir():
        return archiflow_dir

    # Optionally: Search parent directories for project root
    # For now, only check the current working directory

    return None


def get_framework_config_dir() -> Path:
    """
    Get the framework configuration directory.

    Returns:
        Path to framework configuration directory
    """
    # Use the directory containing this file
    return Path(__file__).parent.parent / "config_defaults"


def resolve_config_paths(
    config_type: str,
    working_dir: Optional[Path] = None,
    include_local: bool = True
) -> List[Path]:
    """
    Resolve all configuration paths in precedence order (highest priority last).

    Precedence (highest to lowest):
    1. Project local (.archiflow/config.local.json)
    2. Project (.archiflow/config.json)
    3. Global local (~/.archiflow/config.local.json)
    4. Global (~/.archiflow/config.json)
    5. Framework defaults

    Args:
        config_type: Type of config (e.g., "settings", "ARCHIFLOW")
        working_dir: Current working directory
        include_local: Whether to include .local.* files

    Returns:
        List of paths in order from lowest to highest precedence
    """
    paths = []

    # 1. Framework defaults (lowest precedence)
    framework_dir = get_framework_config_dir()
    framework_path = framework_dir / f"{config_type}.json"
    if framework_path.exists():
        paths.append(framework_path)

    # 2. Global user config
    global_dir = get_global_archiflow_dir()
    global_path = global_dir / f"{config_type}.json"
    if global_path.exists():
        paths.append(global_path)

    # 3. Global local config (gitignored)
    if include_local:
        global_local_path = global_dir / f"{config_type}.local.json"
        if global_local_path.exists():
            paths.append(global_local_path)

    # 4. Project config
    project_dir = get_project_archiflow_dir(working_dir)
    if project_dir:
        project_path = project_dir / f"{config_type}.json"
        if project_path.exists():
            paths.append(project_path)

        # 5. Project local config (gitignored, highest precedence)
        if include_local:
            project_local_path = project_dir / f"{config_type}.local.json"
            if project_local_path.exists():
                paths.append(project_local_path)

    return paths


def resolve_context_paths(
    context_file: str = "ARCHIFLOW.md",
    working_dir: Optional[Path] = None,
    include_local: bool = True
) -> List[Path]:
    """
    Resolve all context file paths in precedence order (highest priority last).

    Args:
        context_file: Name of the context file
        working_dir: Current working directory
        include_local: Whether to include .local.* files

    Returns:
        List of paths in order from lowest to highest precedence
    """
    paths = []

    # 1. Framework defaults (lowest precedence)
    framework_dir = get_framework_config_dir()
    framework_path = framework_dir / context_file
    if framework_path.exists():
        paths.append(framework_path)

    # 2. Global user config
    global_dir = get_global_archiflow_dir()
    global_path = global_dir / context_file
    if global_path.exists():
        paths.append(global_path)

    # 3. Global local config (gitignored)
    if include_local:
        global_local_path = global_dir / context_file.replace(".md", ".local.md")
        if global_local_path.exists():
            paths.append(global_local_path)

    # 4. Project config
    project_dir = get_project_archiflow_dir(working_dir)
    if project_dir:
        project_path = project_dir / context_file
        if project_path.exists():
            paths.append(project_path)

        # 5. Project local config (gitignored, highest precedence)
        if include_local:
            project_local_path = project_dir / context_file.replace(".md", ".local.md")
            if project_local_path.exists():
                paths.append(project_local_path)

    return paths


def resolve_tool_config_path(
    tool_name: str,
    config_file: str = "config.md",
    working_dir: Optional[Path] = None
) -> Optional[Path]:
    """
    Resolve tool-specific configuration path with precedence.

    Precedence: project > global > framework

    Args:
        tool_name: Name of the tool
        config_file: Name of the config file
        working_dir: Current working directory

    Returns:
        Path to the highest-priority config file, or None if not found
    """
    # Check project first
    project_dir = get_project_archiflow_dir(working_dir)
    if project_dir:
        project_tool_dir = project_dir / "tools" / tool_name
        project_path = project_tool_dir / config_file
        if project_path.exists():
            return project_path

    # Check global second
    global_dir = get_global_archiflow_dir()
    global_tool_dir = global_dir / "tools" / tool_name
    global_path = global_tool_dir / config_file
    if global_path.exists():
        return global_path

    # Check framework defaults last
    framework_dir = Path(__file__).parent.parent / "tools" / "prompts" / tool_name
    framework_path = framework_dir / config_file
    if framework_path.exists():
        return framework_path

    return None


def ensure_global_dir() -> Path:
    """
    Ensure the global ArchiFlow directory exists.

    Returns:
        Path to the global directory (created if needed)
    """
    global_dir = get_global_archiflow_dir()
    global_dir.mkdir(parents=True, exist_ok=True)
    return global_dir


def ensure_project_dir(working_dir: Optional[Path] = None) -> Optional[Path]:
    """
    Ensure the project ArchiFlow directory exists.

    Args:
        working_dir: Current working directory

    Returns:
        Path to the project directory (created if needed), or None if not in a project
    """
    if working_dir is None:
        working_dir = Path(os.getcwd())

    # Create the .archiflow directory
    project_dir = working_dir / ".archiflow"
    project_dir.mkdir(parents=True, exist_ok=True)
    return project_dir
