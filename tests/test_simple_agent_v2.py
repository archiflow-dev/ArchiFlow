"""
Tests for the enhanced SimpleAgent v2.
"""

import pytest
from unittest.mock import Mock, MagicMock

from agent_framework.agents.simple_agent_v2 import SimpleAgent
from agent_framework.llm.provider import LLMProvider, LLMResponse
from agent_framework.llm.mock import MockProvider
from agent_framework.messages.types import UserMessage, LLMRespondMessage
from agent_framework.tools.tool_base import ToolRegistry


class TestSimpleAgentV2:
    """Test cases for the enhanced SimpleAgent."""

    def setup_method(self):
        """Set up test fixtures."""
        # Use mock provider
        self.mock_llm = MockProvider(model="gpt-3.5-turbo")
        self.tool_registry = ToolRegistry()

    def test_agent_initialization_general_profile(self):
        """Test initializing SimpleAgent with general profile."""
        agent = SimpleAgent(
            session_id="test_session",
            llm=self.mock_llm,
            profile="general"
        )

        assert agent.profile_name == "general"
        assert agent.session_id == "test_session"
        assert "versatile AI assistant" in agent.system_prompt.lower() or "versatile ai assistant" in agent.system_prompt.lower()
        assert agent.get_capabilities() == ["conversation", "information_retrieval", "basic_analysis"]

    def test_agent_initialization_analyst_profile(self):
        """Test initializing SimpleAgent with analyst profile."""
        agent = SimpleAgent(
            session_id="test_session",
            llm=self.mock_llm,
            profile="analyst"
        )

        assert agent.profile_name == "analyst"
        assert "business analyst" in agent.system_prompt.lower()
        assert agent.get_capabilities() == ["data_analysis", "visualization", "reporting"]

    def test_agent_initialization_custom_prompt(self):
        """Test initializing SimpleAgent with custom prompt."""
        custom_prompt = "You are a custom assistant for testing."
        agent = SimpleAgent(
            session_id="test_session",
            llm=self.mock_llm,
            profile="custom",
            custom_prompt=custom_prompt
        )

        assert agent.system_prompt == custom_prompt
        assert agent.profile is None  # No predefined profile for "custom"

    def test_profile_switching(self):
        """Test switching agent profiles dynamically."""
        agent = SimpleAgent(
            session_id="test_session",
            llm=self.mock_llm,
            profile="general"
        )

        # Switch to analyst profile
        agent.switch_profile("analyst")
        assert agent.profile_name == "analyst"
        assert "business analyst" in agent.system_prompt.lower()

        # Switch with custom prompt
        custom_prompt = "You are a researcher."
        agent.switch_profile("custom", custom_prompt=custom_prompt)
        assert agent.system_prompt == custom_prompt

    def test_get_profile_info(self):
        """Test getting profile information."""
        agent = SimpleAgent(
            session_id="test_session",
            llm=self.mock_llm,
            profile="analyst"
        )

        profile_info = agent.get_profile_info()
        assert profile_info["name"] == "analyst"
        assert "Data analysis" in profile_info["description"]
        assert "data_analysis" in profile_info["capabilities"]
        assert isinstance(profile_info["tools"], list)

    def test_step_with_user_message(self):
        """Test processing a user message."""
        # Set up mock LLM response
        mock_response = LLMResponse(
            content="Hello! How can I help you today?",
            tool_calls=None
        )
        self.mock_llm.generate.return_value = mock_response

        agent = SimpleAgent(
            session_id="test_session",
            llm=self.mock_llm,
            profile="general"
        )

        # Send a user message
        user_msg = UserMessage(
            session_id="test_session",
            sequence=1,
            content="Hello, agent!"
        )

        response = agent.step(user_msg)

        # Check response
        assert isinstance(response, LLMRespondMessage)
        assert response.content == "Hello! How can I help you today?"
        assert response.session_id == "test_session"

    def test_step_with_tool_call(self):
        """Test processing a user message that triggers a tool call."""
        from agent_framework.messages.types import ToolCall, ToolCallMessage
        from agent_framework.tools.read_tool import ReadTool

        # Add a tool to the registry
        read_tool = ReadTool()
        self.tool_registry.register(read_tool)

        # Set up mock LLM response with tool call
        mock_tool_call = Mock()
        mock_tool_call.id = "call_123"
        mock_tool_call.name = "read"
        mock_tool_call.arguments = '{"file_path": "test.txt"}'

        mock_response = LLMResponse(
            content="I'll read the file for you.",
            tool_calls=[mock_tool_call]
        )
        self.mock_llm.generate.return_value = mock_response

        agent = SimpleAgent(
            session_id="test_session",
            llm=self.mock_llm,
            profile="general",
            tools=self.tool_registry
        )

        # Send a user message
        user_msg = UserMessage(
            session_id="test_session",
            sequence=1,
            content="Please read test.txt"
        )

        response = agent.step(user_msg)

        # Check response is a tool call message
        assert isinstance(response, ToolCallMessage)
        assert response.thought == "I'll read the file for you."
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].tool_name == "read"

    def test_add_and_remove_tools(self):
        """Test adding and removing tools dynamically."""
        from agent_framework.tools.read_tool import ReadTool
        from agent_framework.tools.write_tool import WriteTool

        agent = SimpleAgent(
            session_id="test_session",
            llm=self.mock_llm,
            profile="general"
        )

        # Initially has basic tools
        initial_tools = [tool.name for tool in agent.tools.list_tools()]

        # Add a new tool
        read_tool = ReadTool()
        agent.add_tool(read_tool)

        assert "read" in [tool.name for tool in agent.tools.list_tools()]

        # Remove a tool
        agent.remove_tool("read")
        assert "read" not in [tool.name for tool in agent.tools.list_tools()]

    def test_system_message_includes_tools(self):
        """Test that system message includes tool information."""
        from agent_framework.tools.read_tool import ReadTool

        # Add a tool to see it in the system message
        read_tool = ReadTool()
        self.tool_registry.register(read_tool)

        agent = SimpleAgent(
            session_id="test_session",
            llm=self.mock_llm,
            profile="general",
            tools=self.tool_registry
        )

        system_msg = agent.get_system_message()
        assert "Available tools:" in system_msg
        assert "ReadTool" in system_msg or "read" in system_msg

    def test_custom_settings(self):
        """Test providing custom settings during initialization."""
        agent = SimpleAgent(
            session_id="test_session",
            llm=self.mock_llm,
            profile="analyst",
            custom_setting="test_value",
            preferred_chart_type="pie"
        )

        # Check that custom settings are merged
        assert agent.settings.get("custom_setting") == "test_value"
        assert agent.settings.get("preferred_chart_type") == "pie"
        # Profile default should still be there
        assert agent.settings.get("data_format") == "csv"