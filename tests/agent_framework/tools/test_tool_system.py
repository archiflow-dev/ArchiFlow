import unittest
import asyncio
import sys
import os
from typing import List

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../src')))

from agent_framework.tools.tool_base import tool, registry, ToolResult, BaseTool

class TestToolSystem(unittest.TestCase):
    def setUp(self):
        registry.clear()

    def test_tool_decorator_sync(self):
        @tool
        def add(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b
        
        self.assertIn("add", registry.tools)
        tool_obj = registry.get("add")
        self.assertEqual(tool_obj.description, "Add two numbers.")
        self.assertEqual(tool_obj.parameters["properties"]["a"]["type"], "integer")
        
        # Test execution
        result = asyncio.run(tool_obj(a=1, b=2))
        self.assertIsInstance(result, ToolResult)
        self.assertEqual(result.output, "3")

    def test_tool_decorator_async(self):
        @tool
        async def async_add(a: int, b: int) -> int:
            """Async add."""
            return a + b
        
        tool_obj = registry.get("async_add")
        result = asyncio.run(tool_obj(a=1, b=2))
        self.assertEqual(result.output, "3")

    def test_tool_decorator_custom_name(self):
        @tool(name="custom_add", description="Custom description")
        def add(a: int, b: int) -> int:
            return a + b
            
        self.assertIn("custom_add", registry.tools)
        self.assertNotIn("add", registry.tools)
        tool_obj = registry.get("custom_add")
        self.assertEqual(tool_obj.description, "Custom description")

    def test_parameter_inference(self):
        @tool
        def complex_func(a: int, b: str = "default", c: List[int] = []) -> None:
            pass
            
        tool_obj = registry.get("complex_func")
        props = tool_obj.parameters["properties"]
        self.assertEqual(props["a"]["type"], "integer")
        self.assertEqual(props["b"]["type"], "string")
        self.assertEqual(props["c"]["type"], "array")
        self.assertEqual(tool_obj.parameters["required"], ["a"])

    def test_tool_result_return(self):
        @tool
        def raw_tool() -> ToolResult:
            return ToolResult(output="raw", system="sys")
            
        tool_obj = registry.get("raw_tool")
        result = asyncio.run(tool_obj())
        self.assertEqual(result.output, "raw")
        self.assertEqual(result.system, "sys")

    def test_registry_schema(self):
        @tool
        def func1(a: int): pass
        
        @tool
        def func2(b: str): pass
        
        schema = registry.to_llm_schema()
        self.assertEqual(len(schema), 2)
        names = [s["function"]["name"] for s in schema]
        self.assertIn("func1", names)
        self.assertIn("func2", names)
        
        schema_subset = registry.to_llm_schema(["func1"])
        self.assertEqual(len(schema_subset), 1)
        self.assertEqual(schema_subset[0]["function"]["name"], "func1")

if __name__ == '__main__':
    unittest.main()
