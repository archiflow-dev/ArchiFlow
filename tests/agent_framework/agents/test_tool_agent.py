"""Tests for ToolAgent."""
import unittest
from unittest.mock import MagicMock
from src.agent_framework.agents.tool_agent import ToolAgent
from src.agent_framework.messages.types import BaseMessage
from src.agent_framework.config.manager import AgentConfig


class ConcreteToolAgent(ToolAgent):
    """Concrete implementation for testing."""
    
    def get_system_message(self) -> str:
        return "System message"
    
    def step(self, message: BaseMessage) -> None:
        pass
    
    def register_tools(self) -> None:
        # Register a dummy tool
        self.tools.register(MagicMock(name="dummy_tool"))


class TestToolAgent(unittest.TestCase):
    """Test ToolAgent functionality."""
    
    def setUp(self):
        self.mock_llm = MagicMock()
        self.mock_config = AgentConfig(
            llm_provider="mock",
            tools=[],
            max_iterations=10
        )
    
    def test_initialization_calls_register_tools(self):
        """Test that __init__ calls register_tools."""
        agent = ConcreteToolAgent(self.mock_llm, self.mock_config)
        
        # Verify tools were registered (ConcreteToolAgent registers one dummy tool)
        self.assertEqual(len(agent.tools.tools), 1)
        self.assertIn("dummy_tool", agent.tools.tools)


if __name__ == '__main__':
    unittest.main()
