"""
Mock runtime implementation for testing.
"""

from typing import Any, Dict

from agent_framework.runtime.base import ToolRuntime
from agent_framework.runtime.context import ExecutionContext
from agent_framework.runtime.result import ToolResult


class MockRuntime(ToolRuntime):
    """
    Mock runtime for testing purposes.
    
    Always succeeds and returns a predictable result.
    """
    
    def __init__(self, name: str = "mock", always_fail: bool = False):
        """
        Initialize mock runtime.
        
        Args:
            name: Name for this mock runtime
            always_fail: If True, always return failure
        """
        self.name = name
        self.always_fail = always_fail
        self.execution_count = 0
        self.last_tool = None
        self.last_params = None
        self.last_context = None
        self.is_healthy = True
        self.cleaned_up = False
    
    async def execute(
        self,
        tool: "BaseTool",
        params: Dict[str, Any],
        context: ExecutionContext,
    ) -> ToolResult:
        """Execute tool (mock implementation)."""
        self.execution_count += 1
        self.last_tool = tool
        self.last_params = params
        self.last_context = context
        
        tool_name = tool.name if hasattr(tool, 'name') else str(tool)
        
        if self.always_fail:
            return ToolResult.error_result(
                f"Mock failure for {tool_name}",
                execution_time=0.1
            )
        
        return ToolResult.success_result(
            f"Mock output for {tool_name}",
            execution_time=0.1,
            runtime=self.name
        )
    
    async def health_check(self) -> bool:
        """Check health (mock implementation)."""
        return self.is_healthy
    
    async def cleanup(self) -> None:
        """Cleanup (mock implementation)."""
        self.cleaned_up = True


class MockTool:
    """Mock tool for testing."""
    
    def __init__(self, name: str):
        self.name = name
    
    async def execute(self, **params):
        """Mock execute method."""
        return {"result": "mock"}
