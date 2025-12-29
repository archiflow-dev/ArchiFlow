"""
Tests for HistoryManagerBuilder (Task 3.2).

Tests verify:
1. Builder pattern fluent API
2. Preset configurations
3. Configuration validation
4. Integration with HistoryManager
"""
import unittest

from agent_framework.llm.provider import LLMProvider, LLMResponse, FinishReason
from agent_framework.llm.model_config import ModelConfig
from agent_framework.memory.compaction_strategy import (
    SelectiveRetentionStrategy,
    SlidingWindowStrategy,
)
from agent_framework.memory.history_builder import (
    HistoryManagerBuilder,
    HistoryManagerPresets,
)
from agent_framework.memory.message_cleaner import DuplicateCleaner, TODOCleaner
from agent_framework.memory.summarizer import (
    HybridSummarizer,
    LLMSummarizer,
    SimpleSummarizer,
)


class MockLLM(LLMProvider):
    """Mock LLM for testing."""

    def __init__(self):
        super().__init__(model="mock", usage_tracker=None)

    def generate(self, messages, tools=None, **kwargs):
        return LLMResponse(content="Summary", finish_reason=FinishReason.STOP)

    def stream(self, messages, tools=None, **kwargs):
        raise NotImplementedError()


class TestHistoryManagerBuilder(unittest.TestCase):
    """Test HistoryManagerBuilder fluent API."""

    def setUp(self):
        """Set up test fixtures."""
        self.llm = MockLLM()

    def test_minimal_configuration(self):
        """Test minimal valid configuration."""
        history = (
            HistoryManagerBuilder()
            .with_simple_summarizer()
            .build()
        )

        self.assertIsNotNone(history)
        self.assertIsInstance(history.summarizer, SimpleSummarizer)
        self.assertEqual(history.retention_window, 10)  # Default

    def test_builder_requires_summarizer(self):
        """Test that builder requires summarizer."""
        builder = HistoryManagerBuilder()

        with self.assertRaises(ValueError) as ctx:
            builder.build()

        self.assertIn("Summarizer is required", str(ctx.exception))

    def test_with_simple_summarizer(self):
        """Test setting SimpleSummarizer."""
        history = (
            HistoryManagerBuilder()
            .with_simple_summarizer()
            .build()
        )

        self.assertIsInstance(history.summarizer, SimpleSummarizer)

    def test_with_llm_summarizer(self):
        """Test setting LLMSummarizer."""
        history = (
            HistoryManagerBuilder()
            .with_llm_summarizer(self.llm)
            .build()
        )

        self.assertIsInstance(history.summarizer, LLMSummarizer)

    def test_with_hybrid_summarizer(self):
        """Test setting HybridSummarizer."""
        history = (
            HistoryManagerBuilder()
            .with_hybrid_summarizer(self.llm, threshold=7)
            .build()
        )

        self.assertIsInstance(history.summarizer, HybridSummarizer)

    def test_with_max_tokens(self):
        """Test setting max tokens."""
        history = (
            HistoryManagerBuilder()
            .with_simple_summarizer()
            .with_max_tokens(5000)
            .build()
        )

        self.assertEqual(history.max_tokens, 5000)

    def test_with_retention_window(self):
        """Test setting retention window."""
        history = (
            HistoryManagerBuilder()
            .with_simple_summarizer()
            .with_retention_window(20)
            .build()
        )

        self.assertEqual(history.retention_window, 20)

    def test_with_todo_removal(self):
        """Test enabling/disabling TODO removal."""
        # Enabled
        history1 = (
            HistoryManagerBuilder()
            .with_simple_summarizer()
            .with_todo_removal(True)
            .build()
        )
        self.assertTrue(history1.auto_remove_old_todos)

        # Disabled
        history2 = (
            HistoryManagerBuilder()
            .with_simple_summarizer()
            .with_todo_removal(False)
            .build()
        )
        self.assertFalse(history2.auto_remove_old_todos)

    def test_with_proactive_threshold(self):
        """Test setting proactive threshold."""
        history = (
            HistoryManagerBuilder()
            .with_simple_summarizer()
            .with_proactive_threshold(0.75)
            .build()
        )

        self.assertEqual(history.proactive_threshold, 0.75)

    def test_with_selective_retention(self):
        """Test setting SelectiveRetentionStrategy."""
        history = (
            HistoryManagerBuilder()
            .with_simple_summarizer()
            .with_selective_retention()
            .build()
        )

        self.assertIsInstance(history.compaction_strategy, SelectiveRetentionStrategy)

    def test_with_sliding_window(self):
        """Test setting SlidingWindowStrategy."""
        history = (
            HistoryManagerBuilder()
            .with_simple_summarizer()
            .with_sliding_window()
            .build()
        )

        self.assertIsInstance(history.compaction_strategy, SlidingWindowStrategy)

    def test_with_todo_cleaner(self):
        """Test adding TODOCleaner."""
        history = (
            HistoryManagerBuilder()
            .with_simple_summarizer()
            .with_todo_removal(False)  # Disable auto-config
            .with_todo_cleaner()
            .build()
        )

        self.assertEqual(len(history.message_cleaners), 1)
        self.assertIsInstance(history.message_cleaners[0], TODOCleaner)

    def test_with_duplicate_cleaner(self):
        """Test adding DuplicateCleaner."""
        history = (
            HistoryManagerBuilder()
            .with_simple_summarizer()
            .with_todo_removal(False)  # Disable auto-config
            .with_duplicate_cleaner()
            .build()
        )

        self.assertEqual(len(history.message_cleaners), 1)
        self.assertIsInstance(history.message_cleaners[0], DuplicateCleaner)

    def test_with_multiple_cleaners(self):
        """Test adding multiple cleaners."""
        history = (
            HistoryManagerBuilder()
            .with_simple_summarizer()
            .with_todo_removal(False)  # Disable auto-config
            .with_todo_cleaner()
            .with_duplicate_cleaner()
            .build()
        )

        self.assertEqual(len(history.message_cleaners), 2)
        self.assertIsInstance(history.message_cleaners[0], TODOCleaner)
        self.assertIsInstance(history.message_cleaners[1], DuplicateCleaner)

    def test_with_model_config(self):
        """Test setting model config."""
        model_config = ModelConfig(
            model_name="test-model",
            context_window=8000,
            max_output_tokens=2000
        )

        history = (
            HistoryManagerBuilder()
            .with_simple_summarizer()
            .with_model_config(model_config)
            .with_system_prompt_tokens(100)
            .with_tools_tokens(200)
            .build()
        )

        # Should calculate max_tokens from model_config
        self.assertIsNotNone(history.max_tokens)

    def test_fluent_chaining(self):
        """Test that all methods return self for chaining."""
        builder = (
            HistoryManagerBuilder()
            .with_simple_summarizer()
            .with_max_tokens(10000)
            .with_retention_window(15)
            .with_todo_removal(True)
            .with_proactive_threshold(0.8)
            .with_selective_retention()
            .with_duplicate_cleaner()
        )

        # Should be able to build
        history = builder.build()
        self.assertIsNotNone(history)


class TestHistoryManagerPresets(unittest.TestCase):
    """Test HistoryManagerPresets factory methods."""

    def setUp(self):
        """Set up test fixtures."""
        self.llm = MockLLM()

    def test_minimal_preset(self):
        """Test minimal preset configuration."""
        history = HistoryManagerPresets.minimal(max_tokens=5000).build()

        self.assertIsInstance(history.summarizer, SimpleSummarizer)
        self.assertEqual(history.max_tokens, 5000)
        self.assertEqual(history.retention_window, 5)
        self.assertFalse(history.auto_remove_old_todos)

    def test_development_preset(self):
        """Test development preset configuration."""
        history = HistoryManagerPresets.development(self.llm, max_tokens=10000).build()

        self.assertIsInstance(history.summarizer, LLMSummarizer)
        self.assertEqual(history.max_tokens, 10000)
        self.assertEqual(history.retention_window, 10)
        self.assertTrue(history.auto_remove_old_todos)
        self.assertEqual(history.proactive_threshold, 0.8)

    def test_production_preset(self):
        """Test production preset configuration."""
        model_config = ModelConfig(
            model_name="gpt-4",
            context_window=8000,
            max_output_tokens=2000
        )

        history = HistoryManagerPresets.production(self.llm, model_config).build()

        self.assertIsInstance(history.summarizer, HybridSummarizer)
        self.assertEqual(history.retention_window, 15)
        self.assertTrue(history.auto_remove_old_todos)
        self.assertEqual(history.proactive_threshold, 0.75)
        self.assertIsInstance(history.compaction_strategy, SelectiveRetentionStrategy)
        # Should have both TODO and Duplicate cleaners
        self.assertGreaterEqual(len(history.message_cleaners), 1)

    def test_chat_preset(self):
        """Test chat preset configuration."""
        history = HistoryManagerPresets.chat(self.llm, max_tokens=6000).build()

        self.assertIsInstance(history.summarizer, SimpleSummarizer)
        self.assertEqual(history.max_tokens, 6000)
        self.assertEqual(history.retention_window, 20)
        self.assertIsInstance(history.compaction_strategy, SlidingWindowStrategy)
        self.assertFalse(history.auto_remove_old_todos)

    def test_long_conversation_preset(self):
        """Test long conversation preset configuration."""
        history = HistoryManagerPresets.long_conversation(self.llm, max_tokens=20000).build()

        self.assertIsInstance(history.summarizer, HybridSummarizer)
        self.assertEqual(history.max_tokens, 20000)
        self.assertEqual(history.retention_window, 25)
        self.assertTrue(history.auto_remove_old_todos)
        self.assertEqual(history.proactive_threshold, 0.7)

    def test_preset_returns_builder(self):
        """Test that presets return builders for further customization."""
        # Should be able to further customize preset
        history = (
            HistoryManagerPresets.minimal()
            .with_retention_window(10)  # Override preset default
            .with_todo_removal(True)     # Override preset default
            .build()
        )

        self.assertEqual(history.retention_window, 10)
        self.assertTrue(history.auto_remove_old_todos)


class TestBuilderIntegration(unittest.TestCase):
    """Test builder integration with HistoryManager."""

    def setUp(self):
        """Set up test fixtures."""
        self.llm = MockLLM()

    def test_built_history_works_correctly(self):
        """Test that built HistoryManager works as expected."""
        from agent_framework.messages.types import UserMessage

        history = (
            HistoryManagerBuilder()
            .with_simple_summarizer()
            .with_max_tokens(1000)
            .with_retention_window(5)
            .build()
        )

        # Add messages
        history.add(UserMessage(content="Test 1", session_id="test", sequence=0))
        history.add(UserMessage(content="Test 2", session_id="test", sequence=1))

        # Should work normally
        self.assertEqual(len(history.messages), 2)
        llm_format = history.to_llm_format()
        self.assertEqual(len(llm_format), 2)

    def test_builder_vs_direct_construction(self):
        """Test that builder produces equivalent HistoryManager to direct construction."""
        from agent_framework.memory.history import HistoryManager

        # Direct construction
        history1 = HistoryManager(
            summarizer=SimpleSummarizer(),
            max_tokens=5000,
            retention_window=10,
            auto_remove_old_todos=True
        )

        # Builder construction
        history2 = (
            HistoryManagerBuilder()
            .with_simple_summarizer()
            .with_max_tokens(5000)
            .with_retention_window(10)
            .with_todo_removal(True)
            .build()
        )

        # Should have same configuration
        self.assertEqual(history1.max_tokens, history2.max_tokens)
        self.assertEqual(history1.retention_window, history2.retention_window)
        self.assertEqual(history1.auto_remove_old_todos, history2.auto_remove_old_todos)
        self.assertEqual(type(history1.summarizer), type(history2.summarizer))


if __name__ == '__main__':
    unittest.main(verbosity=2)
