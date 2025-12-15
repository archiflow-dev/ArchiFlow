"""
Tests for HistoryManager with model-aware token limits.
"""
import unittest

from src.agent_framework.memory.history import HistoryManager
from src.agent_framework.memory.summarizer import SimpleSummarizer
from src.agent_framework.llm.model_config import ModelConfig
from src.agent_framework.messages.types import UserMessage, SystemMessage


class TestHistoryManagerModelAware(unittest.TestCase):
    """Test HistoryManager with model-aware token limits."""

    def setUp(self):
        """Set up test fixtures."""
        self.model_config = ModelConfig(
            model_name="test-model",
            context_window=128_000,
            max_output_tokens=4_096
        )

    def test_init_with_model_config(self):
        """Test initialization with model_config."""
        history = HistoryManager(
            summarizer=SimpleSummarizer(),
            model_config=self.model_config,
            system_prompt_tokens=1000,
            tools_tokens=2000,
            retention_window=10
        )

        # max_tokens = 128,000 - 1,000 - 2,000 - 4,096 - 500 = 120,404
        self.assertEqual(history.max_tokens, 120_404)
        self.assertEqual(history.retention_window, 10)

    def test_init_with_explicit_max_tokens(self):
        """Test initialization with explicit max_tokens (overrides model_config)."""
        history = HistoryManager(
            summarizer=SimpleSummarizer(),
            model_config=self.model_config,
            max_tokens=50_000  # Explicit override
        )

        self.assertEqual(history.max_tokens, 50_000)

    def test_init_without_model_config_and_max_tokens(self):
        """Test initialization without model_config or max_tokens (uses default)."""
        history = HistoryManager(
            summarizer=SimpleSummarizer(),
            retention_window=10
        )

        # Should use default 4000
        self.assertEqual(history.max_tokens, 4000)

    def test_init_requires_summarizer(self):
        """Test that summarizer is required."""
        with self.assertRaises(ValueError) as context:
            HistoryManager(
                summarizer=None,
                max_tokens=4000
            )

        self.assertIn("summarizer is required", str(context.exception))

    def test_large_context_window_model(self):
        """Test with a large context window model (e.g., Claude)."""
        large_model = ModelConfig(
            model_name="claude-3-5-sonnet",
            context_window=200_000,
            max_output_tokens=8_192
        )

        history = HistoryManager(
            summarizer=SimpleSummarizer(),
            model_config=large_model,
            system_prompt_tokens=2000,
            tools_tokens=3000
        )

        # 200,000 - 2,000 - 3,000 - 8,192 - 500 = 186,308
        self.assertEqual(history.max_tokens, 186_308)

    def test_small_context_window_model(self):
        """Test with a small context window model (e.g., GPT-3.5)."""
        small_model = ModelConfig(
            model_name="gpt-3.5-turbo",
            context_window=16_385,
            max_output_tokens=4_096
        )

        history = HistoryManager(
            summarizer=SimpleSummarizer(),
            model_config=small_model,
            system_prompt_tokens=500,
            tools_tokens=1000
        )

        # 16,385 - 500 - 1,000 - 4,096 - 500 = 10,289
        self.assertEqual(history.max_tokens, 10_289)

    def test_custom_buffer_tokens(self):
        """Test with custom buffer tokens."""
        history = HistoryManager(
            summarizer=SimpleSummarizer(),
            model_config=self.model_config,
            system_prompt_tokens=1000,
            tools_tokens=2000,
            buffer_tokens=1000  # Custom buffer
        )

        # 128,000 - 1,000 - 2,000 - 4,096 - 1,000 = 119,904
        self.assertEqual(history.max_tokens, 119_904)

    def test_compaction_trigger_with_model_config(self):
        """Test that compaction triggers correctly with model-aware limits."""
        history = HistoryManager(
            summarizer=SimpleSummarizer(),
            model_config=self.model_config,
            system_prompt_tokens=1000,
            tools_tokens=2000,
            retention_window=3
        )

        # Add system message
        history.add(SystemMessage(content="System", session_id="test", sequence=0))

        # Add user goal
        history.add(UserMessage(content="Goal", session_id="test", sequence=1))

        # Store initial message count
        initial_count = len(history.messages)

        # Add many messages to exceed token limit
        # With max_tokens of 120,404, we need to add a lot
        for i in range(1000):
            history.add(UserMessage(
                content=f"This is a long message number {i} " * 100,  # Make it long
                session_id="test",
                sequence=2+i
            ))

        # Compaction should have occurred
        self.assertLess(len(history.messages), 1002)  # Less than initial + all added

    def test_backwards_compatibility(self):
        """Test backwards compatibility with old-style initialization."""
        # Old style: explicit max_tokens
        history = HistoryManager(
            summarizer=SimpleSummarizer(),
            max_tokens=8000,
            retention_window=15
        )

        self.assertEqual(history.max_tokens, 8000)
        self.assertEqual(history.retention_window, 15)


if __name__ == "__main__":
    unittest.main()
