import json
import inspect
import functools
import asyncio
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Union, List, Callable, Type

from pydantic import BaseModel, Field

# Import ExecutionContext and path_utils
from ..runtime.context import ExecutionContext
from .path_utils import resolve_path


class ToolResult(BaseModel):
    """Represents the result of a tool execution."""

    output: Any = Field(default=None)
    error: Optional[str] = Field(default=None)
    base64_image: Optional[str] = Field(default=None)
    system: Optional[str] = Field(default=None)

    class Config:
        arbitrary_types_allowed = True

    def __bool__(self):
        return any(getattr(self, field) for field in self.model_fields)

    def __add__(self, other: "ToolResult"):
        def combine_fields(
            field: Optional[str], other_field: Optional[str], concatenate: bool = True
        ):
            if field and other_field:
                if concatenate:
                    return field + other_field
                raise ValueError("Cannot combine tool results")
            return field or other_field

        return ToolResult(
            output=combine_fields(self.output, other.output),
            error=combine_fields(self.error, other.error),
            base64_image=combine_fields(self.base64_image, other.base64_image, False),
            system=combine_fields(self.system, other.system),
        )

    def __str__(self):
        return f"Error: {self.error}" if self.error else str(self.output)

    def replace(self, **kwargs):
        """Returns a new ToolResult with the given fields replaced."""
        # return self.copy(update=kwargs)
        return type(self)(**{**self.model_dump(), **kwargs})


class BaseTool(ABC, BaseModel):
    """Consolidated base class for all tools combining BaseModel and Tool functionality."""

    name: str
    description: str
    parameters: Optional[dict] = None

    # NEW: Execution context with working directory
    execution_context: Optional[ExecutionContext] = Field(
        default=None,
        exclude=True,  # Don't include in schema
        description="Execution context with working directory and constraints"
    )

    class Config:
        arbitrary_types_allowed = True

    async def __call__(self, **kwargs) -> Any:
        """Execute the tool with given parameters."""
        return await self.execute(**kwargs)

    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        """Execute the tool with given parameters."""

    def to_param(self) -> Dict:
        """Convert tool to function call format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def success_response(self, data: Union[Dict[str, Any], str]) -> ToolResult:
        """Create a successful tool result."""
        if isinstance(data, str):
            text = data
        else:
            text = json.dumps(data, indent=2)
        return ToolResult(output=text)

    def fail_response(self, msg: str) -> ToolResult:
        """Create a failed tool result."""
        return ToolResult(error=msg)

    # NEW METHODS for path resolution
    def resolve_path(self, path: str, strict: bool = False) -> str:
        """
        Resolve a file path using the execution context's working directory.

        If the tool has an execution_context with a working_directory set,
        relative paths will be resolved against that directory. Absolute
        paths are returned as-is after normalization.

        Args:
            path: File path (absolute or relative)
            strict: If True, enforce path must be within working_directory

        Returns:
            Resolved absolute path

        Raises:
            ValueError: If strict=True and path resolves outside working_directory
        """
        working_dir = None
        if self.execution_context and self.execution_context.working_directory:
            working_dir = self.execution_context.working_directory

        return resolve_path(path, working_directory=working_dir, strict=strict)

    def get_working_directory(self) -> Optional[str]:
        """
        Get the current working directory from execution context.

        Returns:
            Working directory path or None if not set
        """
        if self.execution_context:
            return self.execution_context.working_directory
        return None


class FunctionTool(BaseTool):
    """Tool wrapper for callable functions."""
    
    func: Callable = Field(exclude=True)
    
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the wrapped function."""
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the wrapped function."""
        if asyncio.iscoroutinefunction(self.func):
            result = await self.func(**kwargs)
        else:
            result = self.func(**kwargs)
        
        if isinstance(result, ToolResult):
            return result
        return self.success_response(str(result))


class ToolRegistry:
    """Singleton registry for tools."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.tools = {}
        return cls._instance
    
    def register(self, tool: BaseTool) -> None:
        """Register a tool."""
        self.tools[tool.name] = tool
    
    def get(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name."""
        return self.tools.get(name)
    
    def list_tools(self) -> List[BaseTool]:
        """Get all registered tools."""
        return list(self.tools.values())
    
    def to_llm_schema(self, tool_names: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Convert tools to LLM-compatible schema.
        
        Args:
            tool_names: Optional list of specific tools to include. If None, all tools.
        """
        if tool_names is None:
            tools_to_convert = self.tools.values()
        else:
            tools_to_convert = [self.tools[name] for name in tool_names if name in self.tools]
        
        return [tool.to_param() for tool in tools_to_convert]
    
    def clear(self) -> None:
        """Clear all tools (useful for testing)."""
        self.tools = {}


# Global registry instance
registry = ToolRegistry()


def _infer_parameters_from_signature(func: Callable) -> Dict[str, Any]:
    """Infer JSON schema from function signature using type hints."""
    sig = inspect.signature(func)
    properties = {}
    required = []
    
    # Type mapping
    type_map = {
        int: "integer",
        float: "number",
        str: "string",
        bool: "boolean",
        list: "array",
        dict: "object"
    }
    
    for param_name, param in sig.parameters.items():
        if param_name in ('self', 'cls'):
            continue
        
        # Get type annotation
        param_type = param.annotation
        json_type = "string"  # default
        
        if param_type != inspect.Parameter.empty:
            # Handle generics like List[int]
            origin = getattr(param_type, "__origin__", None)
            if origin is not None:
                param_type = origin
            
            json_type = type_map.get(param_type, "string")
        
        properties[param_name] = {"type": json_type}
        
        # Check if required (no default value)
        if param.default == inspect.Parameter.empty:
            required.append(param_name)
    
    return {
        "type": "object",
        "properties": properties,
        "required": required
    }


def tool(
    name: Optional[str] = None,
    description: Optional[str] = None,
    parameters: Optional[Dict[str, Any]] = None
):
    """
    Decorator to register a function as a tool.
    
    If parameters is None, automatically infers schema from type hints.
    
    Args:
        name: Tool name. If None, uses function name.
        description: Tool description. If None, uses function docstring.
        parameters: Optional JSON schema. If None, inferred from function signature.
    """
    def decorator(func: Callable):
        tool_name = name or func.__name__
        tool_desc = description or func.__doc__ or "No description provided."
        
        # Auto-infer parameters if not provided
        schema = parameters if parameters is not None else _infer_parameters_from_signature(func)
        
        tool_obj = FunctionTool(
            name=tool_name,
            description=tool_desc,
            func=func,
            parameters=schema
        )
        registry.register(tool_obj)
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        return wrapper
    
    # Handle usage as @tool without arguments
    if callable(name):
        func = name
        name = None
        return decorator(func)
    
    return decorator
