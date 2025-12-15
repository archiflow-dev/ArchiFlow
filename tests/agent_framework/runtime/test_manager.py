"""
Tests for RuntimeManager.
"""

import pytest

from agent_framework.runtime.context import ExecutionContext
from agent_framework.runtime.exceptions import (
    RuntimeNotFoundError,
    SecurityViolation,
)
from agent_framework.runtime.manager import RuntimeManager
from agent_framework.runtime.security import SecurityPolicy, ToolPolicy
from tests.agent_framework.runtime.mocks import MockRuntime, MockTool


class TestRuntimeManager:
    """Tests for RuntimeManager."""
    
    @pytest.fixture
    def manager(self):
        """Create a runtime manager for testing."""
        return RuntimeManager()
    
    @pytest.fixture
    def mock_runtime(self):
        """Create a mock runtime."""
        return MockRuntime("mock")
    
    def test_register_runtime(self, manager, mock_runtime):
        """Test registering a runtime."""
        manager.register_runtime("mock", mock_runtime)
        
        assert "mock" in manager.runtimes
        assert manager.runtimes["mock"] is mock_runtime
    
    def test_unregister_runtime(self, manager, mock_runtime):
        """Test unregistering a runtime."""
        manager.register_runtime("mock", mock_runtime)
        manager.unregister_runtime("mock")
        
        assert "mock" not in manager.runtimes
    
    def test_get_runtime_default(self, manager, mock_runtime):
        """Test getting default runtime."""
        policy = SecurityPolicy(default_runtime="mock")
        manager = RuntimeManager(security_policy=policy)
        manager.register_runtime("mock", mock_runtime)
        
        runtime = manager.get_runtime("any_tool")
        assert runtime is mock_runtime
    
    def test_get_runtime_mapped(self, manager, mock_runtime):
        """Test getting runtime from tool mapping."""
        policy = SecurityPolicy(
            default_runtime="local",
            tool_runtime_map={"bash": "mock"}
        )
        manager = RuntimeManager(security_policy=policy)
        manager.register_runtime("mock", mock_runtime)
        
        runtime = manager.get_runtime("bash")
        assert runtime is mock_runtime
    
    def test_get_runtime_not_found(self, manager):
        """Test getting runtime that doesn't exist."""
        with pytest.raises(RuntimeNotFoundError):
            manager.get_runtime("any_tool")
    
    def test_blocked_tool(self, manager, mock_runtime):
        """Test that blocked tools raise SecurityViolation."""
        policy = SecurityPolicy(blocked_commands=["rm"])
        manager = RuntimeManager(security_policy=policy)
        manager.register_runtime("local", mock_runtime)
        
        with pytest.raises(SecurityViolation):
            manager.get_runtime("rm")
    
    @pytest.mark.asyncio
    async def test_execute_tool(self, manager, mock_runtime):
        """Test executing a tool."""
        manager.register_runtime("local", mock_runtime)
        
        tool = MockTool("test_tool")
        context = ExecutionContext(session_id="test")
        params = {"arg": "value"}
        
        result = await manager.execute_tool(tool, params, context)
        
        assert result.success is True
        assert "Mock output" in result.output
        assert mock_runtime.execution_count == 1
        assert mock_runtime.last_tool is tool
        assert mock_runtime.last_params == params
    
    @pytest.mark.asyncio
    async def test_execute_tool_with_policy_override(self, manager, mock_runtime):
        """Test executing tool with policy override."""
        tool_policy = ToolPolicy(max_execution_time=120)
        policy = SecurityPolicy(
            tool_specific_policies={"test_tool": tool_policy}
        )
        manager = RuntimeManager(security_policy=policy)
        manager.register_runtime("local", mock_runtime)
        
        tool = MockTool("test_tool")
        context = ExecutionContext(session_id="test", timeout=30)
        
        await manager.execute_tool(tool, {}, context)
        
        # Check that override was applied
        assert mock_runtime.last_context.timeout == 120
    
    @pytest.mark.asyncio
    async def test_health_check_all(self, manager):
        """Test health check for all runtimes."""
        runtime1 = MockRuntime("runtime1")
        runtime2 = MockRuntime("runtime2")
        runtime2.is_healthy = False
        
        manager.register_runtime("runtime1", runtime1)
        manager.register_runtime("runtime2", runtime2)
        
        health = await manager.health_check_all()
        
        assert health["runtime1"] is True
        assert health["runtime2"] is False
    
    @pytest.mark.asyncio
    async def test_cleanup_all(self, manager):
        """Test cleanup of all runtimes."""
        runtime1 = MockRuntime("runtime1")
        runtime2 = MockRuntime("runtime2")
        
        manager.register_runtime("runtime1", runtime1)
        manager.register_runtime("runtime2", runtime2)
        
        await manager.cleanup_all()
        
        assert runtime1.cleaned_up is True
        assert runtime2.cleaned_up is True
    
    def test_get_runtime_stats(self, manager, mock_runtime):
        """Test getting runtime statistics."""
        manager.register_runtime("mock", mock_runtime)
        
        stats = manager.get_runtime_stats()
        
        assert stats["total_runtimes"] == 1
        assert "mock" in stats["registered_runtimes"]
        assert stats["default_runtime"] == "local"
