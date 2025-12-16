"""
Core tool loading and management utilities.

This module provides utilities for loading tools by category
and managing tool collections.
"""

from typing import List, Dict, Any, Optional
import importlib
import logging

logger = logging.getLogger(__name__)

from .tool_base import BaseTool, ToolRegistry
from .read_tool import ReadTool
from .write_tool import WriteTool
from .list_tool import ListTool
from .finish_tool import FinishAction

# Try to import web tools, with preference for the more reliable v2 version
WebSearchTool = None
WebFetchTool = None

try:
    from .web_search_tool_v2 import WebSearchToolV2 as WebSearchTool
except ImportError:
    try:
        from .web_search_tool import WebSearchTool
    except ImportError:
        logger.warning("WebSearchTool not available due to missing dependencies")

try:
    from .web_fetch_tool import WebFetchTool
except ImportError:
    logger.warning("WebFetchTool not available due to missing dependencies")

# Tool registry by category
TOOL_REGISTRY = {
    "file": [ReadTool, WriteTool, ListTool],
    "web": [tool for tool in [WebSearchTool, WebFetchTool] if tool is not None],
    "task": [FinishAction],  # Task management tools like finish_task
    # Additional categories will be added as tools are implemented
    "analysis": [],  # Placeholder for data analysis tools
    "communication": [],  # Placeholder for communication tools
    "productivity": [],  # Placeholder for productivity tools
    "development": [],  # Placeholder for development tools
    "system": [],  # Placeholder for system tools
}

# Tool metadata
TOOL_METADATA = {
    "file": {
        "description": "File system operations",
        "tools": {
            "read": "Read file contents",
            "write": "Write content to files",
            "list": "List directory contents"
        }
    },
    "web": {
        "description": "Web interaction tools",
        "tools": {
            "web_search": "Search the web",
            "web_fetch": "Fetch web page content"
        }
    },
    "task": {
        "description": "Task management tools",
        "tools": {
            "finish_task": "Signal that the task is complete"
        }
    }
}

def load_tools_by_category(category: str) -> List[BaseTool]:
    """
    Load all tools belonging to a specific category.

    Args:
        category: The tool category (e.g., "file", "web", "analysis")

    Returns:
        List of initialized tool instances

    Raises:
        ValueError: If the category is not recognized
    """
    if category not in TOOL_REGISTRY:
        raise ValueError(f"Unknown tool category: {category}. Available: {list(TOOL_REGISTRY.keys())}")

    tools = []
    tool_classes = TOOL_REGISTRY[category]

    for tool_class in tool_classes:
        try:
            # Initialize the tool
            tool = tool_class()
            tools.append(tool)
            logger.debug(f"Loaded tool: {tool.name}")
        except Exception as e:
            logger.error(f"Failed to load tool {tool_class.__name__}: {e}")

    return tools

def get_available_categories() -> List[str]:
    """Get list of available tool categories."""
    return list(TOOL_REGISTRY.keys())

def get_tools_in_category(category: str) -> List[str]:
    """Get list of tool names in a category."""
    if category not in TOOL_METADATA:
        return []
    return list(TOOL_METADATA[category]["tools"].keys())

def get_tool_description(category: str, tool_name: str) -> Optional[str]:
    """Get description of a specific tool."""
    if category not in TOOL_METADATA:
        return None
    return TOOL_METADATA[category]["tools"].get(tool_name)

def discover_and_load_tools(module_path: str, category: str) -> None:
    """
    Dynamically discover and load tools from a module.

    Args:
        module_path: Python module path (e.g., "agent_framework.tools.custom")
        category: Category to assign discovered tools to
    """
    try:
        module = importlib.import_module(module_path)

        # Find all BaseTool classes in the module
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (isinstance(attr, type) and
                issubclass(attr, BaseTool) and
                attr != BaseTool):

                # Register the tool class
                if category not in TOOL_REGISTRY:
                    TOOL_REGISTRY[category] = []
                TOOL_REGISTRY[category].append(attr)
                logger.info(f"Discovered tool {attr_name} in category {category}")

    except ImportError as e:
        logger.error(f"Failed to import module {module_path}: {e}")

def register_tool_category(category: str, description: str) -> None:
    """Register a new tool category."""
    if category not in TOOL_REGISTRY:
        TOOL_REGISTRY[category] = []
        TOOL_METADATA[category] = {
            "description": description,
            "tools": {}
        }
        logger.info(f"Registered new tool category: {category}")

def register_tool_class(tool_class: type, category: str) -> None:
    """Register a tool class in a specific category."""
    if category not in TOOL_REGISTRY:
        register_tool_category(category, f"Custom category: {category}")

    TOOL_REGISTRY[category].append(tool_class)

    # Update metadata
    if hasattr(tool_class, '__name__'):
        tool_name = getattr(tool_class, 'name', tool_class.__name__)
        description = getattr(tool_class, 'description', 'No description available')
        TOOL_METADATA[category]["tools"][tool_name] = description

def create_tool_registry_from_categories(categories: List[str]) -> ToolRegistry:
    """
    Create a ToolRegistry containing tools from specified categories.

    Args:
        categories: List of category names to include

    Returns:
        ToolRegistry with tools from the specified categories
    """
    registry = ToolRegistry()

    for category in categories:
        try:
            tools = load_tools_by_category(category)
            for tool in tools:
                registry.register_tool(tool)
        except ValueError as e:
            logger.warning(f"Skipping unknown category {category}: {e}")

    return registry