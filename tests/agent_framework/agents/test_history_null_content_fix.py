"""
Test for null content bug fix in conversation history.

Ensures that ToolCallMessage with empty content is serialized with
empty string, not null, to comply with OpenAI API requirements.
"""

import pytest
from agent_framework.agents.history import ConversationHistory
from agent_framework.messages.types import (
    ToolCallMessage, ToolCall, UserMessage
)


class TestHistoryNullContentFix:
    """Test that tool call messages don't have null content."""

    def test_tool_call_message_with_empty_content(self):
        """Test that ToolCallMessage with empty content serializes to empty string."""
        history = ConversationHistory()

        # Add a user message
        user_msg = UserMessage(
            session_id="test",
            sequence=0,
            content="Test question"
        )
        history.add(user_msg)

        # Add a tool call message with empty thought (default)
        tool_call = ToolCall(
            id="call_123",
            tool_name="test_tool",
            arguments={"param": "value"}
        )
        tool_call_msg = ToolCallMessage(
            session_id="test",
            sequence=1,
            thought="",  # Empty thought
            tool_calls=[tool_call]
        )
        history.add(tool_call_msg)

        # Convert to LLM format
        llm_messages = history.to_llm_format()

        # Find the tool call message
        tool_msg = None
        for msg in llm_messages:
            if msg.get("tool_calls"):
                tool_msg = msg
                break

        assert tool_msg is not None, "Tool call message should be in LLM messages"
        assert "content" in tool_msg, "Tool call message should have content field"
        assert tool_msg["content"] is not None, "Content must not be None/null"
        assert tool_msg["content"] == "", "Content should be empty string"

    def test_tool_call_message_with_text_content(self):
        """Test that ToolCallMessage with text content preserves it."""
        history = ConversationHistory()

        # Add a tool call message with text thought
        tool_call = ToolCall(
            id="call_456",
            tool_name="another_tool",
            arguments={}
        )
        tool_call_msg = ToolCallMessage(
            session_id="test",
            sequence=0,
            thought="I'm going to use this tool",  # Non-empty thought
            tool_calls=[tool_call]
        )
        history.add(tool_call_msg)

        # Convert to LLM format
        llm_messages = history.to_llm_format()

        # Find the tool call message
        tool_msg = llm_messages[0]

        assert tool_msg["content"] == "I'm going to use this tool"
        assert tool_msg["content"] is not None
        assert isinstance(tool_msg["content"], str)

    def test_all_message_contents_are_strings(self):
        """Test that all messages have string content, never None."""
        history = ConversationHistory()

        # Add various message types
        history.add(UserMessage(
            session_id="test",
            sequence=0,
            content="Question"
        ))

        history.add(ToolCallMessage(
            session_id="test",
            sequence=1,
            thought="",  # Empty
            tool_calls=[ToolCall(id="c1", tool_name="tool1", arguments={})]
        ))

        history.add(ToolCallMessage(
            session_id="test",
            sequence=2,
            thought="Using tool",  # Non-empty
            tool_calls=[ToolCall(id="c2", tool_name="tool2", arguments={})]
        ))

        # Convert to LLM format
        llm_messages = history.to_llm_format()

        # Check that no message has None content
        for i, msg in enumerate(llm_messages):
            if "content" in msg:
                assert msg["content"] is not None, \
                    f"Message {i} ({msg.get('role')}) has None content"
                assert isinstance(msg["content"], str), \
                    f"Message {i} ({msg.get('role')}) content is not a string"

    def test_openai_api_format_compliance(self):
        """Test that messages comply with OpenAI API format."""
        history = ConversationHistory()

        # Simulate a conversation with tool calls
        history.add(UserMessage(
            session_id="test",
            sequence=0,
            content="Hello"
        ))

        # Agent responds with tool call (empty content)
        history.add(ToolCallMessage(
            session_id="test",
            sequence=1,
            tool_calls=[
                ToolCall(id="call_abc", tool_name="search", arguments={"q": "test"})
            ]
        ))

        llm_messages = history.to_llm_format()

        # Validate OpenAI format requirements
        for msg in llm_messages:
            # All messages must have a role
            assert "role" in msg
            assert msg["role"] in ["system", "user", "assistant", "tool"]

            # Assistant messages with tool_calls must have string content
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                assert "content" in msg
                assert msg["content"] is not None
                assert isinstance(msg["content"], str)
                # Content can be empty string but not null
                assert msg["content"] == "" or len(msg["content"]) > 0
