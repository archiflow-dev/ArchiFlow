"""
Unit tests for history summarizers.
"""
import unittest
from unittest.mock import Mock, MagicMock

from agent_framework.memory.summarizer import (
    SimpleSummarizer,
    LLMSummarizer,
    HybridSummarizer
)
from agent_framework.messages.types import (
    UserMessage,
    ToolCallMessage,
    ToolResultObservation,
    ToolCall
)
from agent_framework.llm.provider import LLMResponse


class TestSimpleSummarizer(unittest.TestCase):
    """Test SimpleSummarizer."""

    def setUp(self):
        self.summarizer = SimpleSummarizer()

    def test_empty_messages(self):
        """Test summarizing empty message list."""
        result = self.summarizer.summarize([])
        self.assertEqual(result, "[No messages to summarize]")

    def test_single_user_message(self):
        """Test summarizing single user message."""
        messages = [
            UserMessage(
                session_id="test",
                sequence=0,
                content="Hello"
            )
        ]
        result = self.summarizer.summarize(messages)
        self.assertIn("1 messages", result)
        self.assertIn("1 user interaction", result)

    def test_tool_calls_summary(self):
        """Test summarizing messages with tool calls."""
        messages = [
            UserMessage(
                session_id="test",
                sequence=0,
                content="Edit a file"
            ),
            ToolCallMessage(
                session_id="test",
                sequence=1,
                tool_calls=[
                    ToolCall(
                        id="call_1",
                        tool_name="edit",
                        arguments={"file": "test.py"}
                    ),
                    ToolCall(
                        id="call_2",
                        tool_name="bash",
                        arguments={"command": "ls"}
                    )
                ]
            ),
            ToolResultObservation(
                session_id="test",
                sequence=2,
                call_id="call_1",
                content="File edited"
            )
        ]

        result = self.summarizer.summarize(messages)
        self.assertIn("3 messages", result)
        self.assertIn("1 user interaction", result)
        self.assertIn("2 tool call", result)
        self.assertIn("bash", result)
        self.assertIn("edit", result)


class TestLLMSummarizer(unittest.TestCase):
    """Test LLMSummarizer."""

    def setUp(self):
        self.mock_llm = Mock()
        self.summarizer = LLMSummarizer(self.mock_llm, max_summary_tokens=100)

    def test_empty_messages(self):
        """Test summarizing empty message list."""
        result = self.summarizer.summarize([])
        self.assertEqual(result, "[No messages to summarize]")
        self.mock_llm.generate.assert_not_called()

    def test_llm_summarization(self):
        """Test LLM-based summarization."""
        messages = [
            UserMessage(
                session_id="test",
                sequence=0,
                content="Build a web app"
            ),
            ToolCallMessage(
                session_id="test",
                sequence=1,
                tool_calls=[
                    ToolCall(
                        id="call_1",
                        tool_name="edit",
                        arguments={"file": "app.py"}
                    )
                ]
            )
        ]

        # Mock LLM response
        self.mock_llm.generate.return_value = LLMResponse(
            content="User requested to build a web app, edited app.py"
        )

        result = self.summarizer.summarize(messages)

        # Verify LLM was called
        self.mock_llm.generate.assert_called_once()

        # Verify result contains summary
        self.assertIn("Summary of 2 messages", result)
        self.assertIn("User requested to build a web app", result)

    def test_llm_failure_fallback(self):
        """Test fallback when LLM fails."""
        messages = [
            UserMessage(
                session_id="test",
                sequence=0,
                content="Test message"
            )
        ]

        # Mock LLM to raise exception
        self.mock_llm.generate.side_effect = Exception("LLM error")

        result = self.summarizer.summarize(messages)

        # Should fallback to SimpleSummarizer
        self.assertIn("1 messages", result)
        self.assertIn("user interaction", result)

    def test_llm_empty_response_fallback(self):
        """Test fallback when LLM returns empty response."""
        messages = [
            UserMessage(
                session_id="test",
                sequence=0,
                content="Test message"
            )
        ]

        # Mock LLM to return empty content
        self.mock_llm.generate.return_value = LLMResponse(content=None)

        result = self.summarizer.summarize(messages)

        # Should fallback to SimpleSummarizer
        self.assertIn("1 messages", result)


class TestHybridSummarizer(unittest.TestCase):
    """Test HybridSummarizer."""

    def setUp(self):
        self.mock_llm = Mock()
        self.summarizer = HybridSummarizer(
            self.mock_llm,
            threshold=5,
            max_summary_tokens=100
        )

    def test_small_chunk_uses_simple(self):
        """Test that small chunks use SimpleSummarizer."""
        messages = [
            UserMessage(
                session_id="test",
                sequence=i,
                content=f"Message {i}"
            ) for i in range(3)  # Below threshold of 5
        ]

        result = self.summarizer.summarize(messages)

        # Should use SimpleSummarizer, not call LLM
        self.mock_llm.generate.assert_not_called()
        self.assertIn("3 messages", result)

    def test_large_chunk_uses_llm(self):
        """Test that large chunks use LLMSummarizer."""
        messages = [
            UserMessage(
                session_id="test",
                sequence=i,
                content=f"Message {i}"
            ) for i in range(10)  # Above threshold of 5
        ]

        # Mock LLM response
        self.mock_llm.generate.return_value = LLMResponse(
            content="Summary of multiple messages"
        )

        result = self.summarizer.summarize(messages)

        # Should use LLMSummarizer
        self.mock_llm.generate.assert_called_once()
        self.assertIn("Summary of 10 messages", result)
        self.assertIn("Summary of multiple messages", result)

    def test_threshold_boundary(self):
        """Test behavior at threshold boundary."""
        # Exactly at threshold - should use simple
        messages = [
            UserMessage(
                session_id="test",
                sequence=i,
                content=f"Message {i}"
            ) for i in range(5)  # Exactly at threshold
        ]

        result = self.summarizer.summarize(messages)
        self.mock_llm.generate.assert_not_called()

        # One above threshold - should use LLM
        self.mock_llm.reset_mock()
        messages.append(UserMessage(
            session_id="test",
            sequence=5,
            content="Message 5"
        ))

        self.mock_llm.generate.return_value = LLMResponse(
            content="LLM summary"
        )

        result = self.summarizer.summarize(messages)
        self.mock_llm.generate.assert_called_once()


if __name__ == "__main__":
    unittest.main()
