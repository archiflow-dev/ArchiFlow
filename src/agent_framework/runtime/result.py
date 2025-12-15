"""
Tool execution result.

This module defines the ToolResult dataclass that represents
the outcome of tool execution.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ToolResult:
    """
    Result of tool execution.
    
    Contains the outcome of executing a tool, including success status,
    output, errors, and metadata about the execution.
    """
    
    success: bool
    """Whether the tool executed successfully."""
    
    output: Optional[str] = None
    """Output from the tool execution (stdout or return value)."""
    
    error: Optional[str] = None
    """Error message if execution failed."""
    
    execution_time: float = 0.0
    """Execution time in seconds."""
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    """Additional metadata about the execution (runtime used, resource usage, etc.)."""
    
    def __post_init__(self):
        """Validate result after initialization."""
        if self.success and self.error:
            raise ValueError("Successful result should not have an error")
        if not self.success and not self.error:
            raise ValueError("Failed result must have an error message")
    
    @classmethod
    def success_result(
        cls,
        output: str,
        execution_time: float = 0.0,
        **metadata
    ) -> "ToolResult":
        """Create a successful result."""
        return cls(
            success=True,
            output=output,
            execution_time=execution_time,
            metadata=metadata,
        )
    
    @classmethod
    def error_result(
        cls,
        error: str,
        execution_time: float = 0.0,
        **metadata
    ) -> "ToolResult":
        """Create an error result."""
        return cls(
            success=False,
            error=error,
            execution_time=execution_time,
            metadata=metadata,
        )
    
    def __repr__(self) -> str:
        """String representation of the result."""
        status = "SUCCESS" if self.success else "ERROR"
        time_str = f"{self.execution_time:.3f}s"
        
        if self.success:
            output_preview = (
                self.output[:50] + "..." if self.output and len(self.output) > 50
                else self.output or ""
            )
            return f"ToolResult({status}, {time_str}, output={output_preview!r})"
        else:
            return f"ToolResult({status}, {time_str}, error={self.error!r})"
