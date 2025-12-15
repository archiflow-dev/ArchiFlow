"""
Unit tests for BaseAgent.
"""
import unittest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../src')))

from agent_framework.agents.base import BaseAgent, SimpleAgent
from agent_framework.memory.history import HistoryManager
from agent_framework.messages.types import (
    UserMessage, SystemMessage, ToolCallMessage, ToolResultObservation,
    ErrorObservation, StopMessage, LLMRespondMessage, ToolCall
)
from agent_framework.llm.provider import LLMProvider, LLMResponse, FinishReason, ToolCallRequest
from agent_framework.tools.tool_base import ToolRegistry, BaseTool


class MockLLMProvider(LLMProvider):
    """Mock LLM provider for testing."""

    def __init__(self, model: str = "mock", **kwargs):
        super().__init__(model, **kwargs)
        self.responses = []
        self.call_count = 0

    def add_response(self, content: str = None, tool_calls: list = None, finish_reason: FinishReason = FinishReason.STOP):
        """Add a canned response."""
        self.responses.append(LLMResponse(
            content=content,
            tool_calls=tool_calls or [],
            finish_reason=finish_reason,
            usage={"prompt_tokens": 10, "completion_tokens": 20}
        ))

    def generate(self, messages, tools=None, **kwargs):
        """Return next canned response."""
        if self.call_count >= len(self.responses):
            # Default response if none configured
            return LLMResponse(
                content="Default mock response",
                finish_reason=FinishReason.STOP,
                usage={}
            )

        response = self.responses[self.call_count]
        self.call_count += 1
        return response

    def stream(self, messages, tools=None, **kwargs):
        """Not implemented for mock."""
        raise NotImplementedError()


class TestBaseAgent(unittest.TestCase):
    """Test suite for BaseAgent."""

    def setUp(self):
        """Set up test fixtures."""
        self.session_id = "test_session"
        self.mock_llm = MockLLMProvider()
        self.published_messages = []

        def publish_callback(msg):
            self.published_messages.append(msg)

        self.agent = SimpleAgent(
            session_id=self.session_id,
            llm=self.mock_llm,
            publish_callback=publish_callback
        )

    def test_initialization(self):
        """Test agent initialization."""
        self.assertEqual(self.agent.session_id, self.session_id)
        self.assertIsInstance(self.agent.history, HistoryManager)
        self.assertTrue(self.agent.is_running)
        self.assertEqual(self.agent.sequence_counter, 0)

    def test_initialization_with_system_prompt(self):
        """Test agent with system prompt."""
        agent = SimpleAgent(
            session_id="test",
            llm=self.mock_llm,
            system_prompt="You are a helpful assistant"
        )

        self.assertEqual(len(agent.history.messages), 1)
        self.assertIsInstance(agent.history.messages[0], SystemMessage)
        self.assertEqual(agent.history.messages[0].content, "You are a helpful assistant")

    def test_user_message_triggers_llm_call(self):
        """Test that user message triggers LLM call and response."""
        # Configure mock LLM to return a text response
        self.mock_llm.add_response(content="Hello! How can I help you?")

        # Send user message
        user_msg = UserMessage(
            session_id=self.session_id,
            sequence=0,
            content="Hi there"
        )

        self.agent.step(user_msg)

        # Check that message was added to history
        self.assertEqual(len(self.agent.history.messages), 2)
        self.assertIsInstance(self.agent.history.messages[0], UserMessage)
        self.assertIsInstance(self.agent.history.messages[1], LLMRespondMessage)

        # Check that response was published
        self.assertEqual(len(self.published_messages), 1)
        self.assertIsInstance(self.published_messages[0], LLMRespondMessage)
        self.assertEqual(self.published_messages[0].content, "Hello! How can I help you?")

    def test_tool_call_response(self):
        """Test that agent handles tool call responses from LLM."""
        # Configure mock LLM to return tool calls
        tool_call = ToolCallRequest(
            id="call_123",
            name="read_file",
            arguments='{"path": "/tmp/test.txt"}'
        )
        self.mock_llm.add_response(
            content=None,
            tool_calls=[tool_call],
            finish_reason=FinishReason.TOOL_CALLS
        )

        # Send user message
        user_msg = UserMessage(
            session_id=self.session_id,
            sequence=0,
            content="Read the file /tmp/test.txt"
        )

        self.agent.step(user_msg)

        # Check that tool call was published
        self.assertEqual(len(self.published_messages), 1)
        self.assertIsInstance(self.published_messages[0], ToolCallMessage)

        tool_call_msg = self.published_messages[0]
        self.assertEqual(len(tool_call_msg.tool_calls), 1)
        self.assertEqual(tool_call_msg.tool_calls[0].id, "call_123")
        self.assertEqual(tool_call_msg.tool_calls[0].tool_name, "read_file")
        self.assertEqual(tool_call_msg.tool_calls[0].arguments["path"], "/tmp/test.txt")

    def test_tool_result_processing(self):
        """Test that agent processes tool results and continues thinking."""
        # Configure mock LLM to return final response after tool result
        self.mock_llm.add_response(content="The file contains: Hello World")

        # Send tool result
        tool_result = ToolResultObservation(
            session_id=self.session_id,
            sequence=1,
            call_id="call_123",
            content="Hello World",
            status="success"
        )

        self.agent.step(tool_result)

        # Check that LLM was called and response published
        self.assertEqual(len(self.published_messages), 1)
        self.assertIsInstance(self.published_messages[0], LLMRespondMessage)
        self.assertIn("Hello World", self.published_messages[0].content)

    def test_error_handling(self):
        """Test that agent handles errors gracefully."""
        # Configure mock LLM to return response after error
        self.mock_llm.add_response(content="I apologize for the error.")

        # Send error message
        error_msg = ErrorObservation(
            session_id=self.session_id,
            sequence=1,
            content="File not found"
        )

        self.agent.step(error_msg)

        # Agent should continue and try to respond
        self.assertEqual(len(self.published_messages), 1)
        self.assertIsInstance(self.published_messages[0], LLMRespondMessage)

    def test_stop_message(self):
        """Test that stop message halts the agent."""
        stop_msg = StopMessage(
            session_id=self.session_id,
            sequence=1,
            reason="User requested stop"
        )

        self.agent.step(stop_msg)

        self.assertFalse(self.agent.is_running)

        # Further messages should be ignored
        user_msg = UserMessage(
            session_id=self.session_id,
            sequence=2,
            content="Hello"
        )

        self.agent.step(user_msg)

        # No messages published (agent is stopped)
        self.assertEqual(len(self.published_messages), 0)

    def test_sequence_counter(self):
        """Test that sequence numbers increment correctly."""
        self.mock_llm.add_response(content="Response 1")
        self.mock_llm.add_response(content="Response 2")

        # Send two user messages
        msg1 = UserMessage(session_id=self.session_id, sequence=0, content="First")
        msg2 = UserMessage(session_id=self.session_id, sequence=1, content="Second")

        self.agent.step(msg1)
        self.agent.step(msg2)

        # Check sequence numbers
        self.assertEqual(self.published_messages[0].sequence, 0)
        self.assertEqual(self.published_messages[1].sequence, 1)

    def test_history_management(self):
        """Test that conversation history is maintained correctly."""
        self.mock_llm.add_response(content="Hello!")

        user_msg = UserMessage(
            session_id=self.session_id,
            sequence=0,
            content="Hi"
        )

        self.agent.step(user_msg)

        # History should have user message and LLM response
        self.assertEqual(len(self.agent.history.messages), 2)
        self.assertEqual(self.agent.history.messages[0].content, "Hi")
        self.assertEqual(self.agent.history.messages[1].content, "Hello!")

    def test_llm_format_conversion(self):
        """Test that history is correctly converted to LLM format."""
        # Add a user message
        user_msg = UserMessage(
            session_id=self.session_id,
            sequence=0,
            content="Test message"
        )
        self.agent.history.add(user_msg)

        # Get LLM format
        llm_messages = self.agent.history.to_llm_format()

        self.assertEqual(len(llm_messages), 1)
        self.assertEqual(llm_messages[0]["role"], "user")
        self.assertEqual(llm_messages[0]["content"], "Test message")

    def test_tool_with_both_content_and_calls(self):
        """Test handling when LLM returns both content and tool calls."""
        # Some LLMs can return both
        tool_call = ToolCallRequest(
            id="call_456",
            name="calculate",
            arguments='{"expression": "2+2"}'
        )
        self.mock_llm.add_response(
            content="Let me calculate that for you.",
            tool_calls=[tool_call],
            finish_reason=FinishReason.TOOL_CALLS
        )

        user_msg = UserMessage(
            session_id=self.session_id,
            sequence=0,
            content="What is 2+2?"
        )

        self.agent.step(user_msg)

        # Both tool call and response should be published
        self.assertEqual(len(self.published_messages), 2)
        # Tool call first
        self.assertIsInstance(self.published_messages[0], ToolCallMessage)
        # Then response
        self.assertIsInstance(self.published_messages[1], LLMRespondMessage)

    def test_no_publish_callback(self):
        """Test agent works even without publish callback."""
        agent = SimpleAgent(
            session_id="test",
            llm=self.mock_llm,
            publish_callback=None
        )

        self.mock_llm.add_response(content="Test response")

        user_msg = UserMessage(
            session_id="test",
            sequence=0,
            content="Test"
        )

        # Should not raise exception
        agent.step(user_msg)

    def test_agent_name_and_description(self):
        """Test agent metadata methods."""
        self.assertEqual(self.agent.get_name(), "SimpleAgent")
        self.assertTrue(len(self.agent.get_description()) > 0)


class TestAgentWithTools(unittest.TestCase):
    """Test agent with tools."""

    def setUp(self):
        """Set up test fixtures with tools."""
        self.session_id = "test_session"
        self.mock_llm = MockLLMProvider()
        self.published_messages = []

        # Create tool registry
        self.tools = ToolRegistry()

        # Register a simple tool
        class EchoTool(BaseTool):
            name: str = "echo"
            description: str = "Echo the input"
            parameters: dict = {
                "type": "object",
                "properties": {
                    "message": {"type": "string"}
                }
            }

            async def execute(self, **kwargs):
                return self.success_response(kwargs.get("message", ""))

        self.tools.register(EchoTool())

        def publish_callback(msg):
            self.published_messages.append(msg)

        self.agent = SimpleAgent(
            session_id=self.session_id,
            llm=self.mock_llm,
            tools=self.tools,
            publish_callback=publish_callback
        )

    def test_tools_passed_to_llm(self):
        """Test that tools are included in LLM call."""
        self.mock_llm.add_response(content="I can use the echo tool")

        user_msg = UserMessage(
            session_id=self.session_id,
            sequence=0,
            content="What tools do you have?"
        )

        self.agent.step(user_msg)

        # Verify agent has tools
        self.assertEqual(len(self.agent.tools.list_tools()), 1)
        self.assertEqual(self.agent.tools.list_tools()[0].name, "echo")


if __name__ == '__main__':
    unittest.main()
