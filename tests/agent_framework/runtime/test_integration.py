"""
Integration tests for the runtime system.

These tests verify that all runtime components work together correctly.
"""

import asyncio
import pytest

from agent_framework.runtime.context import ExecutionContext
from agent_framework.runtime.local import LocalRuntime
from agent_framework.runtime.manager import RuntimeManager
from agent_framework.runtime.security import SecurityPolicy, ToolPolicy
from tests.agent_framework.runtime.mocks import MockTool


class TestRuntimeManagerIntegration:
    """Integration tests for RuntimeManager with multiple runtimes."""
    
    @pytest.fixture
    def manager(self):
        """Create runtime manager with security policy."""
        policy = SecurityPolicy(
            default_runtime="local",
            tool_runtime_map={
                "special_tool": "local"
            },
            max_execution_time=60,
            max_memory_mb=1024
        )
        return RuntimeManager(security_policy=policy)
    
    @pytest.fixture
    def local_runtime(self):
        """Create local runtime."""
        return LocalRuntime(enable_resource_monitoring=False)
    
    @pytest.mark.asyncio
    async def test_single_runtime_execution(self, manager, local_runtime):
        """Test executing tool with single runtime."""
        manager.register_runtime("local", local_runtime)
        
        tool = MockTool("test_tool")
        context = ExecutionContext(session_id="test")
        
        result = await manager.execute_tool(tool, {}, context)
        
        assert result.success is True
        assert result.metadata['runtime'] == 'local'
    
    @pytest.mark.asyncio
    async def test_runtime_selection_by_policy(self, manager, local_runtime):
        """Test that policy determines runtime selection."""
        manager.register_runtime("local", local_runtime)
        
        # Tool mapped to local runtime
        tool = MockTool("special_tool")
        context = ExecutionContext(session_id="test")
        
        result = await manager.execute_tool(tool, {}, context)
        
        assert result.success is True
        assert manager.last_runtime_used == "local"
    
    @pytest.mark.asyncio
    async def test_tool_specific_policy_override(self, local_runtime):
        """Test that tool-specific policies override defaults."""
        # Create policy with tool-specific override
        tool_policy = ToolPolicy(
            max_execution_time=120,
            allow_network=True
        )
        
        policy = SecurityPolicy(
            default_runtime="local",
            tool_specific_policies={"network_tool": tool_policy}
        )
        
        manager = RuntimeManager(security_policy=policy)
        manager.register_runtime("local", local_runtime)
        
        tool = MockTool("network_tool")
        context = ExecutionContext(
            session_id="test",
            timeout=30,
            allowed_network=False
        )
        
        result = await manager.execute_tool(tool, {}, context)
        
        assert result.success is True
    
    @pytest.mark.asyncio
    async def test_health_check_all_runtimes(self, manager, local_runtime):
        """Test health check across all runtimes."""
        manager.register_runtime("local", local_runtime)
        
        health = await manager.health_check_all()
        
        assert "local" in health
        assert health["local"] is True
    
    @pytest.mark.asyncio
    async def test_cleanup_all_runtimes(self, manager, local_runtime):
        """Test cleanup of all runtimes."""
        manager.register_runtime("local", local_runtime)
        
        await manager.cleanup_all()
        
        # Should not raise errors
    
    @pytest.mark.asyncio
    async def test_concurrent_executions(self, manager, local_runtime):
        """Test concurrent tool executions."""
        manager.register_runtime("local", local_runtime)
        
        tools = [MockTool(f"tool_{i}") for i in range(5)]
        contexts = [ExecutionContext(session_id=f"session_{i}") for i in range(5)]
        
        # Execute all concurrently
        results = await asyncio.gather(*[
            manager.execute_tool(tool, {}, context)
            for tool, context in zip(tools, contexts)
        ])
        
        assert len(results) == 5
        assert all(r.success for r in results)
    
    @pytest.mark.asyncio
    async def test_runtime_stats(self, manager, local_runtime):
        """Test getting runtime statistics."""
        manager.register_runtime("local", local_runtime)
        
        tool = MockTool("test_tool")
        context = ExecutionContext(session_id="test")
        
        await manager.execute_tool(tool, {}, context)
        
        stats = manager.get_runtime_stats()
        
        assert stats['total_runtimes'] == 1
        assert 'local' in stats['registered_runtimes']
        assert stats['last_runtime_used'] == 'local'


class TestMultiRuntimeIntegration:
    """Integration tests with multiple runtime types."""
    
    @pytest.mark.asyncio
    async def test_multiple_runtimes_registered(self):
        """Test registering multiple runtime types."""
        manager = RuntimeManager()
        
        local_runtime = LocalRuntime(enable_resource_monitoring=False)
        manager.register_runtime("local", local_runtime)
        
        # Note: Would register other runtimes here in real scenario
        
        stats = manager.get_runtime_stats()
        assert stats['total_runtimes'] >= 1
    
    @pytest.mark.asyncio
    async def test_runtime_switching(self):
        """Test switching between runtimes based on tool."""
        policy = SecurityPolicy(
            default_runtime="local",
            tool_runtime_map={
                "tool_a": "local",
                "tool_b": "local"  # Would be different runtime in real scenario
            }
        )
        
        manager = RuntimeManager(security_policy=policy)
        local_runtime = LocalRuntime(enable_resource_monitoring=False)
        manager.register_runtime("local", local_runtime)
        
        # Execute different tools
        tool_a = MockTool("tool_a")
        tool_b = MockTool("tool_b")
        context = ExecutionContext(session_id="test")
        
        result_a = await manager.execute_tool(tool_a, {}, context)
        result_b = await manager.execute_tool(tool_b, {}, context)
        
        assert result_a.success is True
        assert result_b.success is True


class TestErrorHandlingIntegration:
    """Integration tests for error handling across runtimes."""
    
    @pytest.mark.asyncio
    async def test_runtime_not_found_error(self):
        """Test error when required runtime not registered."""
        policy = SecurityPolicy(
            tool_runtime_map={"special_tool": "nonexistent"}
        )
        
        manager = RuntimeManager(security_policy=policy)
        
        tool = MockTool("special_tool")
        context = ExecutionContext(session_id="test")
        
        from agent_framework.runtime.exceptions import RuntimeNotFoundError
        
        with pytest.raises(RuntimeNotFoundError):
            await manager.execute_tool(tool, {}, context)
    
    @pytest.mark.asyncio
    async def test_blocked_tool_error(self):
        """Test error when tool is blocked by policy."""
        policy = SecurityPolicy(
            blocked_commands=["dangerous_tool"]
        )
        
        manager = RuntimeManager(security_policy=policy)
        local_runtime = LocalRuntime(enable_resource_monitoring=False)
        manager.register_runtime("local", local_runtime)
        
        tool = MockTool("dangerous_tool")
        context = ExecutionContext(session_id="test")
        
        from agent_framework.runtime.exceptions import SecurityViolation
        
        with pytest.raises(SecurityViolation):
            await manager.execute_tool(tool, {}, context)


class TestConfigurationIntegration:
    """Integration tests for different configurations."""
    
    @pytest.mark.asyncio
    async def test_minimal_configuration(self):
        """Test with minimal configuration."""
        manager = RuntimeManager()
        local_runtime = LocalRuntime()
        
        manager.register_runtime("local", local_runtime)
        
        tool = MockTool("test")
        context = ExecutionContext(session_id="test")
        
        result = await manager.execute_tool(tool, {}, context)
        
        assert result.success is True
        
        await manager.cleanup_all()
    
    @pytest.mark.asyncio
    async def test_full_configuration(self):
        """Test with comprehensive configuration."""
        # Create comprehensive policy
        tool_policies = {
            "network_tool": ToolPolicy(
                max_execution_time=120,
                allow_network=True
            ),
            "compute_tool": ToolPolicy(
                max_execution_time=300,
                max_memory_mb=2048
            )
        }
        
        policy = SecurityPolicy(
            default_runtime="local",
            max_execution_time=60,
            max_memory_mb=1024,
            allow_network=False,
            tool_specific_policies=tool_policies
        )
        
        manager = RuntimeManager(security_policy=policy)
        local_runtime = LocalRuntime(enable_resource_monitoring=True)
        manager.register_runtime("local", local_runtime)
        
        # Execute tools
        tool = MockTool("network_tool")
        context = ExecutionContext(session_id="test")
        
        result = await manager.execute_tool(tool, {}, context)
        
        assert result.success is True
        
        await manager.cleanup_all()
