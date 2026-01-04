"""
Tests for core runtime interfaces and data classes.
"""

import sys
from pathlib import Path

import pytest

project_root = Path(__file__).parent.absolute()
src_path = project_root / "src"

print(f"Project root: {project_root}")
print(f"Adding to sys.path: {src_path}")

# Only add src to path, NOT the project root
sys.path.insert(0, str(src_path))

from agent_framework.runtime.context import ExecutionContext
from agent_framework.runtime.result import ToolResult
from agent_framework.runtime.security import SecurityPolicy, ToolPolicy


class TestExecutionContext:
    """Tests for ExecutionContext."""
    
    def test_create_default_context(self):
        """Test creating context with defaults."""
        context = ExecutionContext(session_id="test-session")
        
        assert context.session_id == "test-session"
        assert context.timeout == 30
        assert context.max_memory_mb == 512
        assert context.max_cpu_percent == 80
        assert context.allowed_network is False
        assert context.working_directory is None
        assert context.environment == {}
    
    def test_create_custom_context(self):
        """Test creating context with custom values."""
        context = ExecutionContext(
            session_id="test-session",
            timeout=60,
            max_memory_mb=1024,
            allowed_network=True,
            environment={"KEY": "value"}
        )
        
        assert context.timeout == 60
        assert context.max_memory_mb == 1024
        assert context.allowed_network is True
        assert context.environment == {"KEY": "value"}
    
    def test_invalid_timeout(self):
        """Test that invalid timeout raises error."""
        with pytest.raises(ValueError, match="timeout must be positive"):
            ExecutionContext(session_id="test", timeout=0)
    
    def test_invalid_memory(self):
        """Test that invalid memory raises error."""
        with pytest.raises(ValueError, match="max_memory_mb must be positive"):
            ExecutionContext(session_id="test", max_memory_mb=-1)
    
    def test_invalid_cpu(self):
        """Test that invalid CPU percentage raises error."""
        with pytest.raises(ValueError, match="max_cpu_percent must be between"):
            ExecutionContext(session_id="test", max_cpu_percent=101)
    
    def test_with_timeout(self):
        """Test creating context with different timeout."""
        context = ExecutionContext(session_id="test")
        new_context = context.with_timeout(120)
        
        assert new_context.timeout == 120
        assert new_context.session_id == context.session_id
        assert new_context.max_memory_mb == context.max_memory_mb
    
    def test_with_network(self):
        """Test creating context with different network setting."""
        context = ExecutionContext(session_id="test")
        new_context = context.with_network(True)
        
        assert new_context.allowed_network is True
        assert new_context.session_id == context.session_id


class TestToolResult:
    """Tests for ToolResult."""
    
    def test_create_success_result(self):
        """Test creating successful result."""
        result = ToolResult.success_result("output text", execution_time=1.5)
        
        assert result.success is True
        assert result.output == "output text"
        assert result.error is None
        assert result.execution_time == 1.5
    
    def test_create_error_result(self):
        """Test creating error result."""
        result = ToolResult.error_result("error message", execution_time=0.5)
        
        assert result.success is False
        assert result.error == "error message"
        assert result.output is None
        assert result.execution_time == 0.5
    
    def test_success_with_metadata(self):
        """Test result with metadata."""
        result = ToolResult.success_result(
            "output",
            runtime="local",
            tool_name="test_tool"
        )
        
        assert result.metadata["runtime"] == "local"
        assert result.metadata["tool_name"] == "test_tool"
    
    def test_invalid_success_with_error(self):
        """Test that success result with error raises ValueError."""
        with pytest.raises(ValueError, match="Successful result should not have an error"):
            ToolResult(success=True, output="output", error="error")
    
    def test_invalid_failure_without_error(self):
        """Test that failed result without error raises ValueError."""
        with pytest.raises(ValueError, match="Failed result must have an error message"):
            ToolResult(success=False, output="output")
    
    def test_repr_success(self):
        """Test string representation of success result."""
        result = ToolResult.success_result("test output", execution_time=1.234)
        repr_str = repr(result)
        
        assert "SUCCESS" in repr_str
        assert "1.234s" in repr_str
        assert "test output" in repr_str
    
    def test_repr_error(self):
        """Test string representation of error result."""
        result = ToolResult.error_result("test error", execution_time=0.5)
        repr_str = repr(result)
        
        assert "ERROR" in repr_str
        assert "0.500s" in repr_str
        assert "test error" in repr_str


class TestSecurityPolicy:
    """Tests for SecurityPolicy."""
    
    def test_default_policy(self):
        """Test default security policy."""
        policy = SecurityPolicy()
        
        assert policy.default_runtime == "local"
        assert policy.max_execution_time == 60
        assert policy.allow_network is False
        assert policy.tool_runtime_map == {}
    
    def test_custom_policy(self):
        """Test custom security policy."""
        policy = SecurityPolicy(
            default_runtime="container",
            max_execution_time=120,
            allow_network=True,
            tool_runtime_map={"bash": "container", "read_file": "local"}
        )
        
        assert policy.default_runtime == "container"
        assert policy.max_execution_time == 120
        assert policy.allow_network is True
    
    def test_get_runtime_for_tool(self):
        """Test getting runtime for specific tool."""
        policy = SecurityPolicy(
            default_runtime="local",
            tool_runtime_map={"bash": "container"}
        )
        
        assert policy.get_runtime_for_tool("bash") == "container"
        assert policy.get_runtime_for_tool("read_file") == "local"
    
    def test_is_tool_allowed(self):
        """Test checking if tool is allowed."""
        policy = SecurityPolicy(
            blocked_commands=["rm", "delete"]
        )
        
        assert policy.is_tool_allowed("read_file") is True
        assert policy.is_tool_allowed("rm") is False
        assert policy.is_tool_allowed("delete") is False
    
    def test_tool_specific_policy(self):
        """Test tool-specific policy overrides."""
        tool_policy = ToolPolicy(
            max_execution_time=300,
            allow_network=True
        )
        
        policy = SecurityPolicy(
            tool_specific_policies={"web_fetch": tool_policy}
        )
        
        retrieved = policy.get_tool_policy("web_fetch")
        assert retrieved is not None
        assert retrieved.max_execution_time == 300
        assert retrieved.allow_network is True
        
        assert policy.get_tool_policy("other_tool") is None
