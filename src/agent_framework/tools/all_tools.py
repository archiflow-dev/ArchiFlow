"""
Unified Tool Registry

This module provides easy access to all available tools.
Import from here to get pre-registered tools.
"""
from .tool_base import registry, ToolRegistry, BaseTool, ToolResult, tool
from .tool_collection import ToolCollection

# Core file operation tools (no external dependencies)
from .read_tool import ReadTool
from .write_tool import WriteTool
from .list_tool import ListTool
from .bash_tool import BashTool, RestrictedBashTool

# Tools with potential dependencies - import with try/except
_optional_tools = []

try:
    from .edit_tool import EditTool
    _optional_tools.append(('EditTool', EditTool))
except ImportError:
    pass

try:
    from .multi_edit_tool import MultiEditTool
    _optional_tools.append(('MultiEditTool', MultiEditTool))
except ImportError:
    pass

try:
    from .glob_tool import GlobTool
    _optional_tools.append(('GlobTool', GlobTool))
except ImportError:
    pass

try:
    from .grep_tool import GrepTool
    _optional_tools.append(('GrepTool', GrepTool))
except ImportError:
    pass

try:
    from .notebook_read_tool import NotebookReadTool
    from .notebook_edit_tool import NotebookEditTool
    _optional_tools.extend([('NotebookReadTool', NotebookReadTool), ('NotebookEditTool', NotebookEditTool)])
except ImportError:
    pass

try:
    from .todo_read_tool import TodoReadTool
    from .todo_write_tool import TodoWriteTool
    _optional_tools.extend([('TodoReadTool', TodoReadTool), ('TodoWriteTool', TodoWriteTool)])
except ImportError:
    pass

try:
    from .todo_read_v2_tool import TodoReadV2Tool
    from .todo_write_v2_tool import TodoWriteV2Tool
    _optional_tools.extend([('TodoReadV2Tool', TodoReadV2Tool), ('TodoWriteV2Tool', TodoWriteV2Tool)])
except ImportError:
    pass

try:
    from .web_fetch_tool import WebFetchTool
    _optional_tools.append(('WebFetchTool', WebFetchTool))
except ImportError:
    pass

try:
    from .web_search_tool import WebSearchTool
    _optional_tools.append(('WebSearchTool', WebSearchTool))
except ImportError:
    pass

try:
    from .finish_tool import FinishAction
    _optional_tools.append(('FinishAction', FinishAction))
except ImportError:
    pass

try:
    from .process_manager_tool import ProcessManagerTool
    _optional_tools.append(('ProcessManagerTool', ProcessManagerTool))
except ImportError:
    pass

try:
    from .prompt_refiner_tool import PromptRefinerTool
    _optional_tools.append(('PromptRefinerTool', PromptRefinerTool))
except ImportError:
    pass

# PPT Tools
try:
    from .ppt.generate_image_tool import GenerateImageTool
    _optional_tools.append(('GenerateImageTool', GenerateImageTool))
except ImportError:
    pass

try:
    from .ppt.export_pptx_tool import ExportPPTXTool
    _optional_tools.append(('ExportPPTXTool', ExportPPTXTool))
except ImportError:
    pass

try:
    from .ppt.export_pdf_tool import ExportPDFTool
    _optional_tools.append(('ExportPDFTool', ExportPDFTool))
except ImportError:
    pass


def register_all_tools():
    """Register all available tools with the global registry."""
    # Core tools (always available)
    core_tools = [
        ReadTool(),
        WriteTool(),
        ListTool(),
        BashTool(),
    ]
    
    for tool in core_tools:
        registry.register(tool)
    
    # Optional tools (only if dependencies are available)
    for name, tool_class in _optional_tools:
        try:
            tool = tool_class()
            registry.register(tool)
        except Exception as e:
            print(f"Warning: Could not register {name}: {e}")
    
    return registry


def get_tool_collection(*tool_names):
    """
    Get a ToolCollection with specified tools.
    
    Args:
        *tool_names: Names of tools to include. If empty, includes all registered tools.
    
    Returns:
        ToolCollection with the specified tools
    """
    if not tool_names:
        tools = registry.list_tools()
    else:
        tools = [registry.get(name) for name in tool_names if registry.get(name)]
    
    return ToolCollection(*tools)


# Auto-register all tools when this module is imported
register_all_tools()


__all__ = [
    # Core
    'registry',
    'ToolRegistry',
    'BaseTool',
    'ToolResult',
    'tool',
    'ToolCollection',
    
    # Functions
    'register_all_tools',
    'get_tool_collection',
    
    # Core tools (always available)
    'ReadTool',
    'WriteTool',
    'ListTool',
    'BashTool',
    'RestrictedBashTool',
]
