"""
Configuration Hierarchy System for ArchiFlow.

This module provides the ConfigHierarchy class that manages the multi-level
configuration system with automatic merging and precedence resolution.

Hierarchy Levels (highest to lowest precedence):
1. Command-line arguments (temporary session override)
2. Environment variables (global env)
3. Local project settings (.archiflow/settings.local.json)
4. Project settings (.archiflow/settings.json)
5. Global user settings (~/.archiflow/settings.json)
6. Framework defaults (embedded in code)
"""
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .paths import (
    get_global_archiflow_dir,
    get_project_archiflow_dir,
    get_framework_config_dir,
    resolve_config_paths,
    resolve_context_paths,
)
from .loader import (
    load_json_file,
    load_markdown_file,
    load_settings_with_precedence,
    parse_frontmatter,
)
from .merger import (
    deep_merge_multiple,
    merge_settings_configs,
    merge_context_files,
)

logger = logging.getLogger(__name__)


@dataclass
class ConfigSnapshot:
    """
    A snapshot of loaded configuration at a specific point in time.

    Attributes:
        settings: The merged settings dictionary
        context: The concatenated context content
        sources: List of source files that were loaded
        metadata: Metadata about the snapshot
    """
    settings: Dict[str, Any] = field(default_factory=dict)
    context: str = ""
    sources: List[Path] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        """Check if the snapshot has valid settings."""
        return bool(self.settings)

    @property
    def has_context(self) -> bool:
        """Check if the snapshot has context content."""
        return bool(self.context.strip())


class ConfigHierarchy:
    """
    Manages the ArchiFlow configuration hierarchy.

    This class provides a unified interface for:
    - Loading settings from multiple hierarchy levels
    - Merging configurations with proper precedence
    - Loading and concatenating context files
    - Caching for performance

    Usage:
        hierarchy = ConfigHierarchy(working_dir=Path.cwd())
        snapshot = hierarchy.load()

        # Access merged settings
        model = snapshot.settings.get("agent", {}).get("defaultModel")

        # Access context
        context = snapshot.context
    """

    def __init__(
        self,
        working_dir: Optional[Path] = None,
        config_type: str = "settings",
        context_file: str = "ARCHIFLOW.md",
        enable_cache: bool = True
    ):
        """
        Initialize the ConfigHierarchy.

        Args:
            working_dir: Current working directory (for project configs)
            config_type: Type of config file (e.g., "settings")
            context_file: Name of the context file
            enable_cache: Whether to enable caching
        """
        self.working_dir = working_dir or Path(os.getcwd())
        self.config_type = config_type
        self.context_file = context_file
        self.enable_cache = enable_cache

        # Cache for loaded configurations
        self._cache: Optional[ConfigSnapshot] = None
        self._cache_key: Optional[str] = None

        # Track last modification times for cache invalidation
        self._mtimes: Dict[Path, float] = {}

        logger.debug(
            f"ConfigHierarchy initialized: working_dir={self.working_dir}, "
            f"config_type={config_type}"
        )

    @property
    def global_dir(self) -> Path:
        """Get the global ArchiFlow directory."""
        return get_global_archiflow_dir()

    @property
    def project_dir(self) -> Optional[Path]:
        """Get the project ArchiFlow directory."""
        return get_project_archiflow_dir(self.working_dir)

    @property
    def framework_dir(self) -> Path:
        """Get the framework configuration directory."""
        return get_framework_config_dir()

    def _get_cache_key(self) -> str:
        """
        Generate a cache key based on current state.

        Returns:
            A string key for caching
        """
        # Include working dir and config type in key
        parts = [str(self.working_dir), self.config_type, self.context_file]

        # Include project dir existence
        if self.project_dir:
            parts.append("with_project")

        return ":".join(parts)

    def _has_files_changed(self) -> bool:
        """
        Check if any configuration files have changed since last load.

        Returns:
            True if files have changed, False otherwise
        """
        if not self._mtimes:
            return True

        # Get all config paths
        config_paths = resolve_config_paths(
            self.config_type,
            working_dir=self.working_dir,
            include_local=True
        )

        # Check if any files have changed
        for path in config_paths:
            if not path.exists():
                continue

            try:
                current_mtime = path.stat().st_mtime
                if path not in self._mtimes:
                    return True
                if current_mtime != self._mtimes[path]:
                    return True
            except OSError:
                return True

        # Check if any files that were tracked are now gone
        for path in self._mtimes:
            if not path.exists():
                return True

        return False

    def _update_mtimes(self, paths: List[Path]) -> None:
        """
        Update modification time tracking for files.

        Args:
            paths: List of file paths to track
        """
        self._mtimes.clear()

        for path in paths:
            if path.exists():
                try:
                    self._mtimes[path] = path.stat().st_mtime
                except OSError:
                    pass

    def clear_cache(self) -> None:
        """Clear the configuration cache."""
        self._cache = None
        self._cache_key = None
        self._mtimes.clear()
        logger.debug("Config cache cleared")

    def load_settings(self, force_reload: bool = False) -> Tuple[Dict[str, Any], List[Path]]:
        """
        Load and merge settings from all hierarchy levels.

        Args:
            force_reload: Force reload even if cache is valid

        Returns:
            Tuple of (merged_settings, source_paths)
        """
        # Load all settings configs
        config_list = load_settings_with_precedence(
            config_type=self.config_type,
            working_dir=self.working_dir,
            include_local=True
        )

        # Extract paths and data
        paths = [path for path, _ in config_list]

        # Merge configs
        merged = merge_settings_configs(config_list)

        logger.info(
            f"Loaded settings from {len(paths)} source(s), "
            f"{len(merged)} top-level keys"
        )

        return merged, paths

    def load_context(self, force_reload: bool = False) -> Tuple[str, List[Path]]:
        """
        Load and concatenate context files from all hierarchy levels.

        Args:
            force_reload: Force reload even if cache is valid

        Returns:
            Tuple of (concatenated_context, source_paths)
        """
        # Get all context file paths
        context_paths = resolve_context_paths(
            context_file=self.context_file,
            working_dir=self.working_dir,
            include_local=True
        )

        if not context_paths:
            return "", []

        # Load each context file
        contexts = []
        for path in context_paths:
            try:
                content = load_markdown_file(path)
                # Add source indicator based on path location
                # Check if path is under global directory (home/.archiflow)
                try:
                    is_global = path.resolve().is_relative_to(self.global_dir)
                except (ValueError, AttributeError):
                    # is_relative_to raises ValueError for relative paths on older Python
                    is_global = self.global_dir in path.resolve().parents or path.resolve() == self.global_dir

                # Check if path is under project directory
                try:
                    is_project = self.project_dir and path.resolve().is_relative_to(self.project_dir)
                except (ValueError, AttributeError):
                    is_project = self.project_dir and (self.project_dir in path.resolve().parents or path.resolve() == self.project_dir)

                if is_global:
                    source = "~/.archiflow/"
                elif is_project:
                    source = "./.archiflow/"
                else:
                    source = "framework/"

                contexts.append((content, source, path))
            except Exception as e:
                logger.warning(f"Failed to load context from {path}: {e}")

        # Concatenate with delimiters
        if contexts:
            parts = []
            for content, source, _ in contexts:
                parts.append(f"### From: {source}{self.context_file}\n\n{content}")

            concatenated = "\n\n---\n\n".join(parts) + "\n\n"
        else:
            concatenated = ""

        paths = [path for _, _, path in contexts]

        logger.info(f"Loaded context from {len(paths)} source(s)")

        return concatenated, paths

    def load(self, force_reload: bool = False) -> ConfigSnapshot:
        """
        Load complete configuration snapshot.

        This loads both settings and context from all hierarchy levels,
        merges them appropriately, and returns a snapshot.

        Args:
            force_reload: Force reload even if cache is valid

        Returns:
            ConfigSnapshot with loaded configuration
        """
        # Check cache
        if self.enable_cache and not force_reload:
            cache_key = self._get_cache_key()

            if self._cache is not None and self._cache_key == cache_key:
                if not self._has_files_changed():
                    logger.debug("Returning cached configuration")
                    return self._cache

        # Load settings
        settings, settings_paths = self.load_settings(force_reload)

        # Load context
        context, context_paths = self.load_context(force_reload)

        # Update mtimes for cache invalidation
        all_paths = settings_paths + context_paths
        self._update_mtimes(all_paths)

        # Create snapshot
        snapshot = ConfigSnapshot(
            settings=settings,
            context=context,
            sources=settings_paths + context_paths,
            metadata={
                "config_type": self.config_type,
                "working_dir": str(self.working_dir),
                "has_project_dir": self.project_dir is not None,
                "settings_sources": [str(p) for p in settings_paths],
                "context_sources": [str(p) for p in context_paths],
            }
        )

        # Update cache
        if self.enable_cache:
            self._cache = snapshot
            self._cache_key = self._get_cache_key()

        return snapshot

    def get_setting(self, key_path: str, default: Any = None) -> Any:
        """
        Get a specific setting value using dot notation.

        Args:
            key_path: Dot-separated path to the setting (e.g., "agent.timeout")
            default: Default value if key not found

        Returns:
            The setting value, or default if not found

        Examples:
            hierarchy = ConfigHierarchy()
            timeout = hierarchy.get_setting("agent.timeout", 300000)
        """
        snapshot = self.load()

        # Navigate to the key
        value = snapshot.settings
        for key in key_path.split("."):
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value

    def get_merged_context(self) -> str:
        """
        Get the merged context content.

        Returns:
            Concatenated context from all hierarchy levels
        """
        snapshot = self.load()
        return snapshot.context

    def reload(self) -> ConfigSnapshot:
        """
        Force reload the configuration.

        Returns:
            Updated ConfigSnapshot
        """
        return self.load(force_reload=True)

    def get_status(self) -> Dict[str, Any]:
        """
        Get status information about the configuration hierarchy.

        Returns:
            Dictionary with status information
        """
        snapshot = self.load()

        return {
            "working_directory": str(self.working_dir),
            "global_dir_exists": self.global_dir.exists(),
            "project_dir_exists": self.project_dir is not None,
            "cache_enabled": self.enable_cache,
            "cache_valid": self._cache is not None,
            "sources_count": len(snapshot.sources),
            "settings_keys": len(snapshot.settings),
            "has_context": snapshot.has_context,
            "sources": [str(p) for p in snapshot.sources],
        }

    def create_project_config(
        self,
        settings: Optional[Dict[str, Any]] = None,
        context: Optional[str] = None
    ) -> Path:
        """
        Create project configuration files.

        Args:
            settings: Settings dictionary to write (optional)
            context: Context content to write (optional)

        Returns:
            Path to the created .archiflow directory

        Raises:
            OSError: If directory creation fails
        """
        # Create the .archiflow directory
        project_dir = self.working_dir / ".archiflow"
        project_dir.mkdir(parents=True, exist_ok=True)

        # Create settings.json if provided
        if settings:
            settings_path = project_dir / f"{self.config_type}.json"
            with open(settings_path, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2)
            logger.info(f"Created settings file: {settings_path}")

        # Create context file if provided
        if context:
            context_path = project_dir / self.context_file
            with open(context_path, "w", encoding="utf-8") as f:
                f.write(context)
            logger.info(f"Created context file: {context_path}")

        # Clear cache to force reload
        self.clear_cache()

        return project_dir


def create_global_config(
    settings: Optional[Dict[str, Any]] = None,
    context: Optional[str] = None
) -> Path:
    """
    Create global configuration files (~/.archiflow/).

    Args:
        settings: Settings dictionary to write (optional)
        context: Context content to write (optional)

    Returns:
        Path to the created .archiflow directory
    """
    global_dir = get_global_archiflow_dir()
    global_dir.mkdir(parents=True, exist_ok=True)

    # Create settings.json if provided
    if settings:
        settings_path = global_dir / "settings.json"
        with open(settings_path, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
        logger.info(f"Created global settings file: {settings_path}")

    # Create context file if provided
    if context:
        context_path = global_dir / "ARCHIFLOW.md"
        with open(context_path, "w", encoding="utf-8") as f:
            f.write(context)
        logger.info(f"Created global context file: {context_path}")

    return global_dir
