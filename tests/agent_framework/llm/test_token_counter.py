"""Tests for token counting implementations."""

import unittest
import json
from unittest.mock import Mock, patch

from agent_framework.llm.token_counter import (
    TiktokenCounter,
    AnthropicCounter,
    FallbackCounter,
    create_token_counter
)


class TestTiktokenCounter(unittest.TestCase):
    """Test TiktokenCounter implementation."""

    def setUp(self):
        """Set up test fixtures."""
        self.counter = TiktokenCounter(model="gpt-4")

    def test_count_simple_message(self):
        """Test counting a simple message."""
        messages = [
            {"role": "user", "content": "Hello, world!"}
        ]

        count = self.counter.count_messages(messages)

        # Should be positive
        self.assertGreater(count, 0)
        # Should be reasonable (not too small or large)
        self.assertGreater(count, 3)  # More than overhead
        self.assertLess(count, 50)  # Less than absurd

    def test_count_multiple_messages(self):
        """Test counting multiple messages."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is 2+2?"},
            {"role": "assistant", "content": "2+2 equals 4."}
        ]

        count = self.counter.count_messages(messages)

        # Should be significantly more than single message
        self.assertGreater(count, 20)

    def test_count_message_with_tool_calls(self):
        """Test counting messages with tool calls."""
        messages = [
            {
                "role": "assistant",
                "content": "I'll read the file",
                "tool_calls": [
                    {
                        "id": "call_123",
                        "type": "function",
                        "function": {
                            "name": "read_file",
                            "arguments": json.dumps({"path": "/test/file.txt"})
                        }
                    }
                ]
            }
        ]

        count = self.counter.count_messages(messages)

        # Should count tool call overhead
        self.assertGreater(count, 15)

    def test_count_text(self):
        """Test counting text directly."""
        text = "This is a test sentence with several words."

        count = self.counter.count_text(text)

        # Should be positive and reasonable
        self.assertGreater(count, 5)
        self.assertLess(count, 30)

    def test_count_empty_messages(self):
        """Test counting empty message list."""
        messages = []

        count = self.counter.count_messages(messages)

        # Should still have base overhead
        self.assertEqual(count, 3)  # Base overhead

    def test_count_message_with_none_values(self):
        """Test handling of None values in messages."""
        messages = [
            {"role": "user", "content": "Test", "name": None}
        ]

        count = self.counter.count_messages(messages)

        # Should not crash, should count successfully
        self.assertGreater(count, 0)

    def test_fallback_when_tiktoken_unavailable(self):
        """Test fallback to rough estimation when tiktoken unavailable."""
        # Create counter and force encoding to None (simulates tiktoken unavailable)
        counter = TiktokenCounter(model="gpt-4")
        counter._encoding = None  # Force unavailable

        # Override encoding property to always return None
        type(counter).encoding = property(lambda self: None)

        messages = [
            {"role": "user", "content": "Test message"}
        ]

        count = counter.count_messages(messages)

        # Should still return a count (using fallback)
        self.assertGreater(count, 0)

    def test_fallback_count_messages(self):
        """Test _fallback_count_messages method."""
        counter = TiktokenCounter(model="gpt-4")

        messages = [
            {"role": "user", "content": "X" * 100}
        ]

        count = counter._fallback_count_messages(messages)

        # Should use chars // 4 estimation
        # Message ~130 chars JSON -> ~32 tokens
        self.assertGreater(count, 20)
        self.assertLess(count, 50)


class TestAnthropicCounter(unittest.TestCase):
    """Test AnthropicCounter implementation."""

    def test_count_with_mock_client(self):
        """Test counting with mocked Anthropic client."""
        mock_client = Mock()
        mock_client.count_tokens.return_value = 42

        counter = AnthropicCounter(client=mock_client)

        messages = [
            {"role": "user", "content": "Test"}
        ]

        count = counter.count_messages(messages)

        self.assertEqual(count, 42)
        mock_client.count_tokens.assert_called_once_with(messages)

    def test_count_without_client(self):
        """Test counting without client (fallback)."""
        counter = AnthropicCounter(client=None)

        messages = [
            {"role": "user", "content": "X" * 100}
        ]

        count = counter.count_messages(messages)

        # Should use fallback
        self.assertGreater(count, 0)

    def test_count_when_client_lacks_method(self):
        """Test handling when client doesn't have count_tokens."""
        mock_client = Mock(spec=[])  # No count_tokens method

        counter = AnthropicCounter(client=mock_client)

        messages = [
            {"role": "user", "content": "Test"}
        ]

        count = counter.count_messages(messages)

        # Should use fallback
        self.assertGreater(count, 0)

    def test_count_when_client_raises_exception(self):
        """Test handling when client raises exception."""
        mock_client = Mock()
        mock_client.count_tokens.side_effect = Exception("API error")

        counter = AnthropicCounter(client=mock_client)

        messages = [
            {"role": "user", "content": "Test"}
        ]

        count = counter.count_messages(messages)

        # Should use fallback
        self.assertGreater(count, 0)

    def test_count_text(self):
        """Test text counting."""
        mock_client = Mock()
        mock_client.count_tokens.return_value = 10

        counter = AnthropicCounter(client=mock_client)

        count = counter.count_text("Test text")

        self.assertEqual(count, 10)

    def test_count_text_without_client(self):
        """Test text counting without client."""
        counter = AnthropicCounter(client=None)

        count = counter.count_text("X" * 100)

        # Should use chars // 4
        self.assertEqual(count, 25)


class TestFallbackCounter(unittest.TestCase):
    """Test FallbackCounter implementation."""

    def test_count_messages(self):
        """Test fallback message counting."""
        counter = FallbackCounter()

        messages = [
            {"role": "user", "content": "X" * 100}
        ]

        count = counter.count_messages(messages)

        # Should use chars // 4 estimation
        self.assertGreater(count, 20)
        self.assertLess(count, 50)

    def test_count_text(self):
        """Test fallback text counting."""
        counter = FallbackCounter()

        count = counter.count_text("X" * 100)

        # Should be 100 // 4 = 25
        self.assertEqual(count, 25)

    def test_count_empty_text(self):
        """Test counting empty text."""
        counter = FallbackCounter()

        count = counter.count_text("")

        # Should return at least 1
        self.assertEqual(count, 1)

    def test_count_message_with_non_serializable_content(self):
        """Test handling of non-JSON-serializable messages."""
        counter = FallbackCounter()

        # Create message with object that can't be JSON serialized
        class NonSerializable:
            pass

        messages = [
            {"role": "user", "content": NonSerializable()}
        ]

        count = counter.count_messages(messages)

        # Should not crash, should use str() fallback
        self.assertGreater(count, 0)

    def test_count_multiple_messages(self):
        """Test counting multiple messages."""
        counter = FallbackCounter()

        messages = [
            {"role": "user", "content": "Message 1"},
            {"role": "assistant", "content": "Response 1"},
            {"role": "user", "content": "Message 2"},
        ]

        count = counter.count_messages(messages)

        # Should be positive
        self.assertGreater(count, 10)


class TestTokenCounterFactory(unittest.TestCase):
    """Test create_token_counter factory function."""

    def test_create_openai_counter(self):
        """Test creating OpenAI counter."""
        counter = create_token_counter("openai", "gpt-4")

        self.assertIsInstance(counter, TiktokenCounter)
        self.assertEqual(counter.model, "gpt-4")

    def test_create_azure_counter(self):
        """Test creating Azure counter (uses tiktoken)."""
        counter = create_token_counter("azure", "gpt-4")

        self.assertIsInstance(counter, TiktokenCounter)

    def test_create_anthropic_counter(self):
        """Test creating Anthropic counter."""
        mock_client = Mock()
        counter = create_token_counter("anthropic", "claude-3", client=mock_client)

        self.assertIsInstance(counter, AnthropicCounter)
        self.assertEqual(counter.client, mock_client)

    def test_create_unknown_counter(self):
        """Test creating counter for unknown provider."""
        counter = create_token_counter("unknown-provider", "unknown-model")

        self.assertIsInstance(counter, FallbackCounter)

    def test_case_insensitive_provider(self):
        """Test provider matching is case-insensitive."""
        counter1 = create_token_counter("OpenAI", "gpt-4")
        counter2 = create_token_counter("OPENAI", "gpt-4")
        counter3 = create_token_counter("openai", "gpt-4")

        self.assertIsInstance(counter1, TiktokenCounter)
        self.assertIsInstance(counter2, TiktokenCounter)
        self.assertIsInstance(counter3, TiktokenCounter)


class TestTokenCountingAccuracy(unittest.TestCase):
    """Integration tests for token counting accuracy."""

    def test_tiktoken_consistency(self):
        """Test that tiktoken counting is consistent."""
        counter = TiktokenCounter(model="gpt-4")

        messages = [
            {"role": "user", "content": "What is 2+2?"}
        ]

        count1 = counter.count_messages(messages)
        count2 = counter.count_messages(messages)

        # Should be deterministic
        self.assertEqual(count1, count2)

    def test_message_overhead_calculation(self):
        """Test that message overhead is correctly calculated."""
        counter = TiktokenCounter(model="gpt-4")

        # Empty message should have base overhead
        empty_messages = []
        empty_count = counter.count_messages(empty_messages)

        # One empty message should have more overhead
        one_message = [{"role": "user", "content": ""}]
        one_count = counter.count_messages(one_message)

        # One message should have more tokens than no messages
        self.assertGreater(one_count, empty_count)

    def test_longer_content_has_more_tokens(self):
        """Test that longer content results in more tokens."""
        counter = TiktokenCounter(model="gpt-4")

        short_messages = [{"role": "user", "content": "Hi"}]
        long_messages = [{"role": "user", "content": "X" * 1000}]

        short_count = counter.count_messages(short_messages)
        long_count = counter.count_messages(long_messages)

        self.assertGreater(long_count, short_count)

    def test_fallback_counter_conservative(self):
        """Test that fallback counter provides reasonable estimates."""
        fallback = FallbackCounter()
        tiktoken_counter = TiktokenCounter(model="gpt-4")

        messages = [
            {"role": "user", "content": "X" * 100}
        ]

        fallback_count = fallback.count_messages(messages)

        # If tiktoken is available, compare
        if tiktoken_counter.encoding is not None:
            tiktoken_count = tiktoken_counter.count_messages(messages)

            # Fallback should be in same ballpark (within 2x)
            self.assertLess(abs(fallback_count - tiktoken_count) / tiktoken_count, 1.0)


if __name__ == '__main__':
    unittest.main()
