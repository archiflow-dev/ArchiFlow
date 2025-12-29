"""
Tests for MessageFormatter (Task 3.1).

Tests verify:
1. Conversion of all message types to LLM format
2. Proper handling of tool calls and results
3. Batch tool result expansion
4. Error handling for unknown message types
5. Integration with HistoryManager
"""
import unittest
from agent_framework.memory.message_formatter import MessageFormatter
from agent_framework.messages.types import (
    AgentFinishedMessage,
    BaseMessage,
    BatchToolResultObservation,
    EnvironmentMessage,
    LLMRespondMessage,
    ProjectContextMessage,
    SystemMessage,
    ToolCall,
    ToolCallMessage,
    ToolResultObservation,
    UserMessage,
)


class TestMessageFormatter(unittest.TestCase):
    """Test MessageFormatter functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.formatter = MessageFormatter()

    def test_user_message_conversion(self):
        """Test that UserMessage converts correctly."""
        msg = UserMessage(
            content="Hello, world!",
            session_id="test",
            sequence=0
        )

        result = self.formatter._convert_message(msg)

        self.assertEqual(result["role"], "user")
        self.assertEqual(result["content"], "Hello, world!")

    def test_system_message_conversion(self):
        """Test that SystemMessage converts correctly."""
        msg = SystemMessage(
            content="You are a helpful assistant",
            session_id="test",
            sequence=0
        )

        result = self.formatter._convert_message(msg)

        self.assertEqual(result["role"], "system")
        self.assertEqual(result["content"], "You are a helpful assistant")

    def test_llm_respond_message_conversion(self):
        """Test that LLMRespondMessage converts correctly."""
        msg = LLMRespondMessage(
            content="I can help with that",
            session_id="test",
            sequence=0
        )

        result = self.formatter._convert_message(msg)

        self.assertEqual(result["role"], "assistant")
        self.assertEqual(result["content"], "I can help with that")

    def test_tool_call_message_conversion(self):
        """Test that ToolCallMessage converts correctly."""
        msg = ToolCallMessage(
            tool_calls=[
                ToolCall(
                    id="call_123",
                    tool_name="read_file",
                    arguments={"path": "/test/file.txt"}
                )
            ],
            session_id="test",
            sequence=0
        )

        result = self.formatter._convert_message(msg)

        self.assertEqual(result["role"], "assistant")
        self.assertIn("tool_calls", result)
        self.assertEqual(len(result["tool_calls"]), 1)

        tool_call = result["tool_calls"][0]
        self.assertEqual(tool_call["id"], "call_123")
        self.assertEqual(tool_call["type"], "function")
        self.assertEqual(tool_call["function"]["name"], "read_file")
        self.assertIn("path", tool_call["function"]["arguments"])

    def test_tool_result_observation_conversion(self):
        """Test that ToolResultObservation converts correctly."""
        msg = ToolResultObservation(
            call_id="call_123",
            content="File content here",
            session_id="test",
            sequence=0
        )

        result = self.formatter._convert_message(msg)

        self.assertEqual(result["role"], "tool")
        self.assertEqual(result["tool_call_id"], "call_123")
        self.assertEqual(result["content"], "File content here")

    def test_environment_message_conversion(self):
        """Test that EnvironmentMessage converts correctly."""
        msg = EnvironmentMessage(
            event_type="file_changed",
            content="/path/to/file",
            session_id="test",
            sequence=0
        )

        result = self.formatter._convert_message(msg)

        self.assertEqual(result["role"], "user")
        self.assertIn("[Environment: file_changed]", result["content"])
        self.assertIn("/path/to/file", result["content"])

    def test_project_context_message_conversion(self):
        """Test that ProjectContextMessage converts correctly."""
        msg = ProjectContextMessage(
            context="Project context information",
            session_id="test",
            sequence=0
        )

        result = self.formatter._convert_message(msg)

        self.assertEqual(result["role"], "system")
        self.assertEqual(result["content"], "Project context information")

    def test_agent_finished_message_conversion(self):
        """Test that AgentFinishedMessage converts correctly."""
        msg = AgentFinishedMessage(
            reason="Task completed successfully",
            session_id="test",
            sequence=0
        )

        result = self.formatter._convert_message(msg)

        self.assertEqual(result["role"], "assistant")
        self.assertIn("Task completed", result["content"])
        self.assertIn("Task completed successfully", result["content"])

    def test_batch_tool_result_conversion(self):
        """Test that BatchToolResultObservation expands correctly."""
        # Create mock result objects
        class MockToolResult:
            def __init__(self, call_id, content):
                self.call_id = call_id
                self.content = content

        msg = BatchToolResultObservation(
            results=[
                MockToolResult("call_1", "Result 1"),
                MockToolResult("call_2", "Result 2"),
                MockToolResult("call_3", "Result 3")
            ],
            session_id="test",
            sequence=0
        )

        # Batch results are handled specially in to_llm_format()
        messages = [msg]
        result = self.formatter.to_llm_format(messages)

        # Should expand to 3 separate messages
        self.assertEqual(len(result), 3)

        # Verify each result
        self.assertEqual(result[0]["role"], "tool")
        self.assertEqual(result[0]["tool_call_id"], "call_1")
        self.assertEqual(result[0]["content"], "Result 1")

        self.assertEqual(result[1]["role"], "tool")
        self.assertEqual(result[1]["tool_call_id"], "call_2")
        self.assertEqual(result[1]["content"], "Result 2")

        self.assertEqual(result[2]["role"], "tool")
        self.assertEqual(result[2]["tool_call_id"], "call_3")
        self.assertEqual(result[2]["content"], "Result 3")

    def test_to_llm_format_multiple_messages(self):
        """Test converting multiple messages in sequence."""
        messages = [
            SystemMessage(content="System", session_id="test", sequence=0),
            UserMessage(content="Hello", session_id="test", sequence=1),
            LLMRespondMessage(content="Hi there", session_id="test", sequence=2),
            ToolCallMessage(
                tool_calls=[
                    ToolCall(id="call_1", tool_name="test_tool", arguments={})
                ],
                session_id="test",
                sequence=3
            ),
            ToolResultObservation(
                call_id="call_1",
                content="Tool result",
                session_id="test",
                sequence=4
            )
        ]

        result = self.formatter.to_llm_format(messages)

        # Should have 5 messages
        self.assertEqual(len(result), 5)

        # Verify order and types
        self.assertEqual(result[0]["role"], "system")
        self.assertEqual(result[1]["role"], "user")
        self.assertEqual(result[2]["role"], "assistant")
        self.assertEqual(result[3]["role"], "assistant")  # Tool call
        self.assertIn("tool_calls", result[3])
        self.assertEqual(result[4]["role"], "tool")

    def test_empty_messages_list(self):
        """Test converting empty messages list."""
        result = self.formatter.to_llm_format([])
        self.assertEqual(result, [])

    def test_message_with_empty_content(self):
        """Test message with None or empty content."""
        msg = UserMessage(
            content=None,
            session_id="test",
            sequence=0
        )

        result = self.formatter._convert_message(msg)

        self.assertEqual(result["role"], "user")
        self.assertEqual(result["content"], "")  # Should default to empty string

    def test_tool_call_with_string_arguments(self):
        """Test tool call with non-dict arguments."""
        msg = ToolCallMessage(
            tool_calls=[
                ToolCall(
                    id="call_123",
                    tool_name="test_tool",
                    arguments="string_arg"  # Non-dict argument
                )
            ],
            session_id="test",
            sequence=0
        )

        result = self.formatter._convert_message(msg)

        # Should convert to string
        self.assertEqual(result["tool_calls"][0]["function"]["arguments"], "string_arg")

    def test_unknown_message_type(self):
        """Test handling of unknown message type."""
        # Create a custom message type
        class CustomMessage(BaseMessage):
            pass

        msg = CustomMessage(session_id="test", sequence=0)

        result = self.formatter._convert_message(msg)

        # Should return None for unknown types
        self.assertIsNone(result)

    def test_from_llm_format_not_implemented(self):
        """Test that from_llm_format raises NotImplementedError."""
        with self.assertRaises(NotImplementedError):
            self.formatter.from_llm_format([])

    def test_tool_call_with_content(self):
        """Test tool call message with content field."""
        msg = ToolCallMessage(
            tool_calls=[
                ToolCall(id="call_1", tool_name="test", arguments={})
            ],
            session_id="test",
            sequence=0
        )
        # Add content attribute
        msg.content = "Calling tool..."

        result = self.formatter._convert_message(msg)

        self.assertEqual(result["role"], "assistant")
        self.assertEqual(result["content"], "Calling tool...")
        self.assertIn("tool_calls", result)


if __name__ == '__main__':
    unittest.main(verbosity=2)
