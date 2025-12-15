"""Tests for tool system."""
import unittest
import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../src')))

from agent_framework.tools.tool_base import (
    BaseTool, FunctionTool, ToolRegistry, tool, registry, _infer_parameters_from_signature, ToolResult
)


class TestParameterInference(unittest.TestCase):
    """Test automatic parameter schema inference."""
    
    def test_infer_simple_types(self):
        """Test inference of basic types."""
        def sample_func(name: str, age: int, score: float) -> str:
            return "test"
        
        schema = _infer_parameters_from_signature(sample_func)
        
        self.assertEqual(schema["type"], "object")
        self.assertIn("name", schema["properties"])
        self.assertEqual(schema["properties"]["name"]["type"], "string")
        self.assertEqual(schema["properties"]["age"]["type"], "integer")
        self.assertEqual(schema["properties"]["score"]["type"], "number")
        self.assertEqual(set(schema["required"]), {"name", "age", "score"})
    
    def test_infer_optional_params(self):
        """Test inference with default values."""
        def sample_func(required: str, optional: int = 10) -> str:
            return "test"
        
        schema = _infer_parameters_from_signature(sample_func)
        
        self.assertEqual(schema["required"], ["required"])
        self.assertNotIn("optional", schema["required"])
    
    def test_infer_no_annotations(self):
        """Test inference without type hints defaults to string."""
        def sample_func(param1, param2):
            return "test"
        
        schema = _infer_parameters_from_signature(sample_func)
        
        self.assertEqual(schema["properties"]["param1"]["type"], "string")
        self.assertEqual(schema["properties"]["param2"]["type"], "string")


class TestToolDecorator(unittest.TestCase):
    """Test @tool decorator."""
    
    def setUp(self):
        registry.clear()
    
    def test_decorator_with_auto_inference(self):
        """Test decorator automatically infers schema."""
        @tool(name="add", description="Add numbers")
        def add(a: int, b: int) -> int:
            return a + b
        
        tool_obj = registry.get("add")
        self.assertIsNotNone(tool_obj)
        self.assertEqual(tool_obj.name, "add")
        
        # Check inferred schema
        params = tool_obj.parameters
        self.assertIn("a", params["properties"])
        self.assertEqual(params["properties"]["a"]["type"], "integer")
        self.assertEqual(set(params["required"]), {"a", "b"})
    
    def test_decorator_with_manual_schema(self):
        """Test decorator with manually provided schema."""
        manual_schema = {
            "type": "object",
            "properties": {"custom": {"type": "string"}},
            "required": ["custom"]
        }
        
        @tool(name="custom", description="Custom tool", parameters=manual_schema)
        def custom_tool(x):
            return x
        
        tool_obj = registry.get("custom")
        self.assertEqual(tool_obj.parameters, manual_schema)
    
    def test_decorated_function_still_callable(self):
        """Test that decorated function remains callable."""
        @tool(name="multiply", description="Multiply")
        def multiply(a: int, b: int) -> int:
            return a * b
        
        result = multiply(3, 4)
        self.assertEqual(result, 12)


class TestToolRegistry(unittest.TestCase):
    """Test ToolRegistry."""
    
    def setUp(self):
        self.registry = ToolRegistry()
        self.registry.clear()
    
    def test_register_and_get(self):
        """Test registering and retrieving tools."""
        def test_func():
            return "test"
        
        tool_obj = FunctionTool(
            name="test",
            description="Test tool",
            func=test_func,
            parameters={}
        )
        
        self.registry.register(tool_obj)
        retrieved = self.registry.get("test")
        
        self.assertEqual(retrieved.name, "test")
    
    def test_get_nonexistent(self):
        """Test getting non-existent tool returns None."""
        result = self.registry.get("nonexistent")
        self.assertIsNone(result)
    
    def test_list_tools(self):
        """Test listing all tools."""
        @tool(name="tool1", description="First")
        def tool1():
            pass
        
        @tool(name="tool2", description="Second")
        def tool2():
            pass
        
        tools = self.registry.list_tools()
        self.assertEqual(len(tools), 2)
        tool_names = {t.name for t in tools}
        self.assertEqual(tool_names, {"tool1", "tool2"})
    
    def test_to_llm_schema(self):
        """Test converting tools to LLM schema."""
        @tool(name="greet", description="Greet someone")
        def greet(name: str) -> str:
            return f"Hello {name}"
        
        schemas = self.registry.to_llm_schema()
        
        self.assertEqual(len(schemas), 1)
        self.assertEqual(schemas[0]["type"], "function")
        self.assertEqual(schemas[0]["function"]["name"], "greet")
        self.assertIn("parameters", schemas[0]["function"])
    
    def test_to_llm_schema_filtered(self):
        """Test converting specific tools to schema."""
        @tool(name="tool1", description="First")
        def tool1():
            pass
        
        @tool(name="tool2", description="Second")
        def tool2():
            pass
        
        schemas = self.registry.to_llm_schema(tool_names=["tool1"])
        
        self.assertEqual(len(schemas), 1)
        self.assertEqual(schemas[0]["function"]["name"], "tool1")


class TestFunctionTool(unittest.TestCase):
    """Test FunctionTool execution."""
    
    def test_execute(self):
        """Test tool execution."""
        def add(a: int, b: int) -> int:
            return a + b
        
        tool_obj = FunctionTool(
            name="add",
            description="Add",
            func=add,
            parameters={}
        )
        
        # Execute is now async and returns ToolResult
        result = asyncio.run(tool_obj.execute(a=2, b=3))
        self.assertIsInstance(result, ToolResult)
        self.assertEqual(result.output, "5")
    
    def test_execute_with_error(self):
        """Test tool execution with error."""
        def failing_func():
            raise ValueError("Test error")
        
        tool_obj = FunctionTool(
            name="fail",
            description="Fails",
            func=failing_func,
            parameters={}
        )
        
        # New behavior: catches exception and returns error in ToolResult
        result = asyncio.run(tool_obj.execute())
        self.assertIsInstance(result, ToolResult)
        self.assertEqual(result.error, "Test error")


class TestBaseToolPathResolution(unittest.TestCase):
    """Test BaseTool path resolution with ExecutionContext."""

    def test_resolve_path_without_context(self):
        """BaseTool should resolve absolute paths without context."""
        from agent_framework.tools.read_tool import ReadTool

        tool = ReadTool()
        # Absolute path should resolve to itself
        if os.name == 'nt':
            result = tool.resolve_path("C:\\absolute\\path.py")
            assert "path.py" in result
        else:
            result = tool.resolve_path("/absolute/path.py")
            assert "/absolute/path.py" in result

    def test_resolve_path_with_context(self):
        """BaseTool should use context's working_directory for relative paths."""
        from agent_framework.tools.read_tool import ReadTool
        from agent_framework.runtime.context import ExecutionContext
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            tool = ReadTool()
            tool.execution_context = ExecutionContext(
                session_id="test",
                working_directory=tmpdir
            )

            result = tool.resolve_path("src/main.py")
            expected = str(Path(tmpdir) / "src" / "main.py")
            assert result == expected

    def test_get_working_directory(self):
        """BaseTool should return working directory from context."""
        from agent_framework.tools.read_tool import ReadTool
        from agent_framework.runtime.context import ExecutionContext

        tool = ReadTool()
        assert tool.get_working_directory() is None

        tool.execution_context = ExecutionContext(
            session_id="test",
            working_directory="/project"
        )
        assert tool.get_working_directory() == "/project"

    def test_resolve_path_strict_mode(self):
        """BaseTool should enforce strict mode when requested."""
        from agent_framework.tools.read_tool import ReadTool
        from agent_framework.runtime.context import ExecutionContext
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            tool = ReadTool()
            tool.execution_context = ExecutionContext(
                session_id="test",
                working_directory=tmpdir
            )

            # Should allow paths within working directory
            result = tool.resolve_path("src/main.py", strict=True)
            assert tmpdir in result

            # Should block paths outside working directory
            with self.assertRaises(ValueError) as ctx:
                tool.resolve_path("../../etc/passwd", strict=True)
            assert "outside working directory" in str(ctx.exception)


if __name__ == '__main__':
    unittest.main()
