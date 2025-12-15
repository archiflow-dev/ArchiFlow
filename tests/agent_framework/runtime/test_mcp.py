"""
Tests for MCP runtime components.
"""

import pytest

from agent_framework.runtime.context import ExecutionContext
from agent_framework.runtime.mcp.adapter import MCPToolAdapter, MCPToolRegistry
from agent_framework.runtime.mcp.config import MCPServerConfig
from agent_framework.runtime.mcp.runtime import MCPRuntime
from agent_framework.runtime.mcp.server_manager import (
    MCPServerManager,
    MCPSession,
    MCPToolInfo,
    ToolsListResult,
    TextContent,
    CallToolResult,
)


class TestMCPServerConfig:
    """Tests for MCPServerConfig."""
    
    def test_create_config(self):
        """Test creating a server config."""
        config = MCPServerConfig(
            name="test-server",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
            env={"NODE_ENV": "production"}
        )
        
        assert config.name == "test-server"
        assert config.command == "npx"
        assert len(config.args) == 3
        assert config.transport == "stdio"
    
    def test_invalid_transport(self):
        """Test that invalid transport raises error."""
        with pytest.raises(ValueError, match="Invalid transport"):
            MCPServerConfig(
                name="test",
                command="test",
                transport="invalid"
            )
    
    def test_empty_name(self):
        """Test that empty name raises error."""
        with pytest.raises(ValueError, match="name cannot be empty"):
            MCPServerConfig(name="", command="test")


class TestMCPToolAdapter:
    """Tests for MCPToolAdapter."""
    
    @pytest.fixture
    def mock_session(self):
        """Create a mock MCP session."""
        import asyncio
        
        class MockProcess:
            pid = 12345
        
        return MCPSession("test-server", MockProcess())
    
    def test_create_adapter(self, mock_session):
        """Test creating a tool adapter."""
        adapter = MCPToolAdapter(
            server_name="test-server",
            tool_name="read_file",
            description="Read a file",
            input_schema={"type": "object", "required": ["path"]},
            session=mock_session
        )
        
        assert adapter.name == "test-server.read_file"
        assert adapter.server_name == "test-server"
        assert adapter._mcp_tool_name == "read_file"
    
    def test_get_schema(self, mock_session):
        """Test getting tool schema."""
        adapter = MCPToolAdapter(
            server_name="test-server",
            tool_name="read_file",
            description="Read a file",
            input_schema={"type": "object", "required": ["path"]},
            session=mock_session
        )
        
        schema = adapter.get_schema()
        
        assert schema["name"] == "test-server.read_file"
        assert schema["description"] == "Read a file"
        assert "required" in schema["parameters"]
    
    def test_validate_params_missing_required(self, mock_session):
        """Test parameter validation with missing required field."""
        adapter = MCPToolAdapter(
            server_name="test-server",
            tool_name="read_file",
            description="Read a file",
            input_schema={"type": "object", "required": ["path"]},
            session=mock_session
        )
        
        with pytest.raises(ValueError, match="Missing required parameter: path"):
            adapter._validate_params({})
    
    @pytest.mark.asyncio
    async def test_execute(self, mock_session):
        """Test executing a tool."""
        adapter = MCPToolAdapter(
            server_name="test-server",
            tool_name="test_tool",
            description="Test tool",
            input_schema={"type": "object"},
            session=mock_session
        )
        
        result = await adapter.execute()
        
        assert result.success is True
        assert "Mock result" in result.output


class TestMCPToolRegistry:
    """Tests for MCPToolRegistry."""
    
    @pytest.fixture
    def registry(self):
        """Create a tool registry."""
        return MCPToolRegistry()
    
    @pytest.fixture
    def mock_tool(self):
        """Create a mock tool adapter."""
        import asyncio
        
        class MockProcess:
            pid = 12345
        
        session = MCPSession("test-server", MockProcess())
        
        return MCPToolAdapter(
            server_name="test-server",
            tool_name="test_tool",
            description="Test tool",
            input_schema={},
            session=session
        )
    
    def test_register_tool(self, registry, mock_tool):
        """Test registering a tool."""
        registry.register(mock_tool)
        
        assert len(registry.tools) == 1
        assert "test-server.test_tool" in registry.tools
    
    def test_get_tool(self, registry, mock_tool):
        """Test getting a tool."""
        registry.register(mock_tool)
        
        tool = registry.get("test-server.test_tool")
        
        assert tool is not None
        assert tool.name == "test-server.test_tool"
    
    def test_list_all(self, registry, mock_tool):
        """Test listing all tools."""
        registry.register(mock_tool)
        
        tools = registry.list_all()
        
        assert len(tools) == 1
        assert tools[0].name == "test-server.test_tool"
    
    def test_list_by_server(self, registry, mock_tool):
        """Test listing tools by server."""
        registry.register(mock_tool)
        
        tools = registry.list_by_server("test-server")
        
        assert len(tools) == 1
        assert tools[0].server_name == "test-server"
    
    def test_get_schemas(self, registry, mock_tool):
        """Test getting all schemas."""
        registry.register(mock_tool)
        
        schemas = registry.get_schemas()
        
        assert len(schemas) == 1
        assert schemas[0]["name"] == "test-server.test_tool"
    
    def test_clear(self, registry, mock_tool):
        """Test clearing registry."""
        registry.register(mock_tool)
        registry.clear()
        
        assert len(registry.tools) == 0
        assert len(registry.tools_by_server) == 0
    
    def test_get_stats(self, registry, mock_tool):
        """Test getting statistics."""
        registry.register(mock_tool)
        
        stats = registry.get_stats()
        
        assert stats["total_tools"] == 1
        assert "test-server" in stats["servers"]


class TestMCPRuntime:
    """Tests for MCPRuntime."""
    
    @pytest.fixture
    def runtime(self):
        """Create an MCP runtime."""
        # Create with empty config for testing
        return MCPRuntime(server_configs=[])
    
    def test_create_runtime(self):
        """Test creating runtime."""
        config = MCPServerConfig(
            name="test-server",
            command="echo",
            args=["test"]
        )
        
        runtime = MCPRuntime(server_configs=[config])
        
        assert len(runtime.server_configs) == 1
        assert runtime.retry_attempts == 3
        assert not runtime._initialized
    
    @pytest.mark.asyncio
    async def test_initialize_empty(self, runtime):
        """Test initializing with no servers."""
        await runtime.initialize()
        
        assert runtime._initialized is True
        assert len(runtime.tool_registry.tools) == 0
    
    @pytest.mark.asyncio
    async def test_health_check_not_initialized(self, runtime):
        """Test health check before initialization."""
        is_healthy = await runtime.health_check()
        
        assert is_healthy is False
    
    @pytest.mark.asyncio
    async def test_cleanup(self, runtime):
        """Test cleanup."""
        await runtime.initialize()
        await runtime.cleanup()
        
        assert runtime._initialized is False
        assert len(runtime.tool_registry.tools) == 0
    
    def test_get_stats(self, runtime):
        """Test getting statistics."""
        stats = runtime.get_stats()
        
        assert "initialized" in stats
        assert "servers_configured" in stats
        assert "tools_discovered" in stats
    
    @pytest.mark.asyncio
    async def test_execute_non_mcp_tool(self, runtime):
        """Test executing non-MCP tool returns error."""
        await runtime.initialize()
        
        class NonMCPTool:
            name = "test"
        
        tool = NonMCPTool()
        context = ExecutionContext(session_id="test")
        
        result = await runtime.execute(tool, {}, context)
        
        assert result.success is False
        assert "not an MCP tool" in result.error
