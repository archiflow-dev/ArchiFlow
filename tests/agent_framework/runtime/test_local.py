"""
Tests for LocalRuntime.
"""

import asyncio
import pytest
from pathlib import Path
import sys
project_root = Path(__file__).parent.parent.parent.parent.absolute()
src_path = project_root / "src"

print(f"Project root: {project_root}")
print(f"Adding to sys.path: {src_path}")

# Only add src to path, NOT the project root
sys.path.insert(0, str(src_path))

from agent_framework.runtime.context import ExecutionContext
from agent_framework.runtime.exceptions import (
    ExecutionError,
    ResourceLimitError,
    TimeoutError as RuntimeTimeoutError,
)
from agent_framework.runtime.local import LocalRuntime
from tests.agent_framework.runtime.mocks import MockTool


class SlowTool:
    """Tool that takes a long time to execute."""
    
    def __init__(self, sleep_time: float):
        self.name = "slow_tool"
        self.sleep_time = sleep_time
    
    async def execute(self, **params):
        """Sleep for specified time."""
        await asyncio.sleep(self.sleep_time)
        return "completed"


class MemoryHogTool:
    """Tool that allocates a lot of memory."""
    
    def __init__(self):
        self.name = "memory_hog"
    
    async def execute(self, size_mb: int = 100):
        """Allocate memory."""
        # Allocate approximately size_mb megabytes
        data = bytearray(size_mb * 1024 * 1024)
        await asyncio.sleep(0.5)  # Keep it allocated
        return f"allocated {size_mb}MB"


class FailingTool:
    """Tool that always fails."""
    
    def __init__(self):
        self.name = "failing_tool"
    
    async def execute(self, **params):
        """Raise an error."""
        raise ValueError("Tool execution failed")


class SyncTool:
    """Synchronous tool (not async)."""
    
    def __init__(self):
        self.name = "sync_tool"
    
    def execute(self, value: str = "test"):
        """Synchronous execute method."""
        return f"sync result: {value}"


class TestLocalRuntime:
    """Tests for LocalRuntime."""
    
    @pytest.fixture
    def runtime(self):
        """Create a local runtime for testing."""
        return LocalRuntime(enable_resource_monitoring=True)
    
    @pytest.fixture
    def context(self):
        """Create an execution context."""
        return ExecutionContext(session_id="test-session")
    
    @pytest.mark.asyncio
    async def test_execute_simple_tool(self, runtime, context):
        """Test executing a simple tool."""
        tool = MockTool("test_tool")
        params = {"arg": "value"}
        
        result = await runtime.execute(tool, params, context)
        
        assert result.success is True
        assert "mock" in result.output.lower()
        assert result.execution_time > 0
        assert result.metadata["runtime"] == "local"
    
    @pytest.mark.asyncio
    async def test_execute_sync_tool(self, runtime, context):
        """Test executing a synchronous tool."""
        tool = SyncTool()
        params = {"value": "hello"}
        
        result = await runtime.execute(tool, params, context)
        
        assert result.success is True
        assert "sync result: hello" in result.output
    
    @pytest.mark.asyncio
    async def test_timeout_enforcement(self, runtime):
        """Test that timeout is enforced."""
        tool = SlowTool(sleep_time=5.0)
        context = ExecutionContext(session_id="test", timeout=1)
        
        with pytest.raises(RuntimeTimeoutError) as exc_info:
            await runtime.execute(tool, {}, context)
        
        assert exc_info.value.timeout == 1
    
    @pytest.mark.asyncio
    async def test_tool_execution_error(self, runtime, context):
        """Test handling of tool execution errors."""
        tool = FailingTool()
        
        result = await runtime.execute(tool, {}, context)
        
        assert result.success is False
        assert "Tool execution failed" in result.error
        assert result.metadata.get("exception_type") == "ValueError"
    
    @pytest.mark.asyncio
    async def test_execution_time_tracking(self, runtime, context):
        """Test that execution time is tracked."""
        tool = SlowTool(sleep_time=0.5)
        
        result = await runtime.execute(tool, {}, context)
        
        assert result.success is True
        assert result.execution_time >= 0.5
        assert result.execution_time < 1.0  # Should not be too long
    
    @pytest.mark.asyncio
    async def test_health_check(self, runtime):
        """Test health check."""
        is_healthy = await runtime.health_check()
        assert is_healthy is True
    
    @pytest.mark.asyncio
    async def test_cleanup(self, runtime):
        """Test cleanup (should be no-op)."""
        await runtime.cleanup()
        # Should not raise any errors
    
    @pytest.mark.asyncio
    async def test_resource_monitoring_disabled(self):
        """Test runtime with resource monitoring disabled."""
        runtime = LocalRuntime(enable_resource_monitoring=False)
        tool = MockTool("test")
        context = ExecutionContext(session_id="test")
        
        result = await runtime.execute(tool, {}, context)
        
        assert result.success is True
    
    def test_get_current_memory(self, runtime):
        """Test getting current memory usage."""
        memory_mb = runtime.get_current_memory_mb()
        
        assert memory_mb > 0
        assert memory_mb < 10000  # Reasonable upper bound
    
    def test_get_current_cpu(self, runtime):
        """Test getting current CPU usage."""
        cpu_percent = runtime.get_current_cpu_percent()
        
        assert cpu_percent >= 0
        assert cpu_percent <= 100
    
    @pytest.mark.asyncio
    async def test_tool_without_execute_method(self, runtime, context):
        """Test error when tool doesn't have execute method."""
        class BadTool:
            name = "bad_tool"
        
        tool = BadTool()
        
        result = await runtime.execute(tool, {}, context)
        
        assert result.success is False
        assert "does not have execute method" in result.error


class TestLocalRuntimeIntegration:
    """Integration tests for LocalRuntime."""
    
    @pytest.mark.asyncio
    async def test_concurrent_executions(self):
        """Test multiple concurrent tool executions."""
        runtime = LocalRuntime()
        
        tools = [MockTool(f"tool_{i}") for i in range(5)]
        contexts = [ExecutionContext(session_id=f"session_{i}") for i in range(5)]
        
        # Execute all tools concurrently
        results = await asyncio.gather(*[
            runtime.execute(tool, {}, context)
            for tool, context in zip(tools, contexts)
        ])
        
        # All should succeed
        assert all(r.success for r in results)
        assert len(results) == 5
    
    @pytest.mark.asyncio
    async def test_timeout_with_cleanup(self):
        """Test that timeout properly cleans up monitoring."""
        runtime = LocalRuntime(enable_resource_monitoring=True)
        tool = SlowTool(sleep_time=10.0)
        context = ExecutionContext(session_id="test", timeout=0.5)
        
        with pytest.raises(RuntimeTimeoutError):
            await runtime.execute(tool, {}, context)
        
        # Runtime should still be healthy after timeout
        assert await runtime.health_check()
