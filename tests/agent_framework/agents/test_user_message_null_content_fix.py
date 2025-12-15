"""
Test for UserMessage null content bug fix.

This test ensures that UserMessage with None content is properly handled
when converting to LLM format, preventing OpenAI API errors.

Bug: When UserMessage.from_dict() receives {'content': None}, it creates
a message with content=None, which OpenAI API rejects with:
"Invalid value for 'content': expected a string, got null."

Fix: All message content fields in to_llm_format() now use `content or ""`
to ensure None values are converted to empty strings.
"""

import pytest
from agent_framework.agents.history import ConversationHistory
from agent_framework.messages.types import UserMessage, SystemMessage, ToolResultObservation


class TestUserMessageNullContentFix:
    """Test that UserMessage with None content doesn't break LLM format conversion."""

    def test_user_message_with_none_content_from_dict(self):
        """Test that UserMessage.from_dict with None content converts to empty string."""
        # This is the bug scenario: dict with explicit None content
        msg = UserMessage.from_dict({
            'session_id': 'test',
            'sequence': 0,
            'content': None  # Explicit None
        })

        # UserMessage will have None content (overrides default)
        assert msg.content is None, "UserMessage should have None content from dict"

        # But when converted to LLM format, it should become empty string
        history = ConversationHistory()
        history.add(msg)
        llm_messages = history.to_llm_format()

        assert len(llm_messages) == 1
        assert llm_messages[0]["role"] == "user"
        assert llm_messages[0]["content"] is not None, "Content must not be None"
        assert llm_messages[0]["content"] == "", "Content should be empty string"

    def test_user_message_with_empty_string_content(self):
        """Test that UserMessage with empty string content remains empty string."""
        msg = UserMessage(session_id='test', sequence=0, content="")

        history = ConversationHistory()
        history.add(msg)
        llm_messages = history.to_llm_format()

        assert llm_messages[0]["content"] == ""

    def test_user_message_with_normal_content(self):
        """Test that UserMessage with normal content is preserved."""
        msg = UserMessage(session_id='test', sequence=0, content="Hello world")

        history = ConversationHistory()
        history.add(msg)
        llm_messages = history.to_llm_format()

        assert llm_messages[0]["content"] == "Hello world"

    def test_all_message_types_handle_none_content(self):
        """Test that all message types handle None content gracefully."""
        history = ConversationHistory()

        # UserMessage with None
        user_msg = UserMessage.from_dict({
            'session_id': 'test',
            'sequence': 0,
            'content': None
        })
        history.add(user_msg)

        # SystemMessage with None
        sys_msg = SystemMessage.from_dict({
            'session_id': 'test',
            'sequence': 1,
            'content': None
        })
        history.add(sys_msg)

        # ToolResultObservation with None
        tool_result = ToolResultObservation.from_dict({
            'session_id': 'test',
            'sequence': 2,
            'call_id': 'call_123',
            'content': None
        })
        history.add(tool_result)

        # Convert to LLM format
        llm_messages = history.to_llm_format()

        # All should have empty string content, not None
        for msg in llm_messages:
            assert "content" in msg
            assert msg["content"] is not None, f"Message {msg['role']} has None content"
            assert isinstance(msg["content"], str), f"Message {msg['role']} content is not string"

    def test_brainstorm_scenario_reproduction(self):
        """
        Reproduce the actual bug scenario from brainstorm command.

        This simulates the flow where:
        1. Brainstorm sends initial greeting as UserMessage
        2. Agent responds with tool calls
        3. Tool results come back
        4. User sends their actual message

        The bug occurred when a UserMessage with None content was in the history.
        """
        history = ConversationHistory()

        # Greeting (sent by brainstorm command)
        greeting = UserMessage(
            session_id='test',
            sequence=0,
            content="Hello! I'm ready to help..."
        )
        history.add(greeting)

        # Simulate a scenario where somehow a UserMessage with None gets added
        # (This could happen from deserialization bugs or edge cases)
        bad_msg = UserMessage.from_dict({
            'session_id': 'test',
            'sequence': 3,
            'content': None  # The bug!
        })
        history.add(bad_msg)

        # User's actual message
        user_msg = UserMessage(
            session_id='test',
            sequence=4,
            content="Build a coding agent system"
        )
        history.add(user_msg)

        # Convert to LLM format - this should NOT fail
        llm_messages = history.to_llm_format()

        # Verify all messages are valid
        assert len(llm_messages) == 3
        for i, msg in enumerate(llm_messages):
            assert msg["content"] is not None, f"Message {i} has None content"
            assert isinstance(msg["content"], str), f"Message {i} content not string"

        # Verify the bad message was converted to empty string
        assert llm_messages[1]["content"] == ""
        assert llm_messages[2]["content"] == "Build a coding agent system"

    def test_openai_api_compliance_with_none_values(self):
        """Test that messages with None values comply with OpenAI API requirements."""
        history = ConversationHistory()

        # Add messages with None content (edge case)
        history.add(UserMessage.from_dict({
            'session_id': 'test',
            'sequence': 0,
            'content': None
        }))

        llm_messages = history.to_llm_format()

        # Validate OpenAI API requirements
        for msg in llm_messages:
            assert "role" in msg
            assert "content" in msg
            assert msg["content"] is not None, "OpenAI API rejects None content"
            assert isinstance(msg["content"], str), "Content must be string"

    def test_fix_prevents_openai_400_error(self):
        """
        Verify the fix prevents the specific OpenAI API 400 error.

        Error was:
        "Invalid value for 'content': expected a string, got null."
        """
        history = ConversationHistory()

        # Create the exact scenario that caused the bug
        msg = UserMessage.from_dict({
            'session_id': 'test',
            'sequence': 0,
            'content': None  # This caused: "expected a string, got null"
        })
        history.add(msg)

        llm_messages = history.to_llm_format()

        # The fix ensures content is never None
        assert llm_messages[0]["content"] == ""  # Empty string, not None

        # This would now be valid for OpenAI API
        # (In real usage, this dict would be sent as JSON to OpenAI)
        import json
        try:
            json_str = json.dumps(llm_messages[0])
            parsed = json.loads(json_str)
            assert parsed["content"] == ""
            assert parsed["content"] is not None
        except Exception as e:
            pytest.fail(f"Message serialization failed: {e}")
