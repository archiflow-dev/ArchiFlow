"""Configuration package."""

# Path resolution
from .paths import (
    get_global_archiflow_dir,
    get_project_archiflow_dir,
    get_framework_config_dir,
    resolve_config_paths,
    resolve_context_paths,
    resolve_tool_config_path,
    ensure_global_dir,
    ensure_project_dir,
)

# Configuration loading
from .loader import (
    ConfigLoadError,
    load_json_file,
    load_json_with_defaults,
    load_markdown_file,
    concatenate_markdown_files,
    load_settings_with_precedence,
    load_context_with_precedence,
    parse_frontmatter,
    load_tool_config,
)

# Configuration merging
from .merger import (
    deep_merge,
    deep_merge_multiple,
    merge_with_precedence,
    merge_settings_configs,
    merge_context_files,
    merge_lists_with_append,
    merge_lists_unique,
    deep_merge_with_list_strategy,
    get_effective_value,
)

__all__ = [
    # Path resolution
    "get_global_archiflow_dir",
    "get_project_archiflow_dir",
    "get_framework_config_dir",
    "resolve_config_paths",
    "resolve_context_paths",
    "resolve_tool_config_path",
    "ensure_global_dir",
    "ensure_project_dir",
    # Configuration loading
    "ConfigLoadError",
    "load_json_file",
    "load_json_with_defaults",
    "load_markdown_file",
    "concatenate_markdown_files",
    "load_settings_with_precedence",
    "load_context_with_precedence",
    "parse_frontmatter",
    "load_tool_config",
    # Configuration merging
    "deep_merge",
    "deep_merge_multiple",
    "merge_with_precedence",
    "merge_settings_configs",
    "merge_context_files",
    "merge_lists_with_append",
    "merge_lists_unique",
    "deep_merge_with_list_strategy",
    "get_effective_value",
]
