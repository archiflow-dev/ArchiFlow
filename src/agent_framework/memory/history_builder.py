"""
Builder pattern for HistoryManager configuration.

This module provides a fluent API for configuring HistoryManager instances
and presets for common use cases.
"""
import logging
from typing import Optional

from ..llm.model_config import ModelConfig
from .compaction_strategy import (
    CompactionStrategy,
    SelectiveRetentionStrategy,
    SlidingWindowStrategy,
)
from .message_cleaner import (
    CompositeCleaner,
    DuplicateCleaner,
    MessageCleaner,
    TODOCleaner,
)
from .summarizer import (
    HistorySummarizer,
    HybridSummarizer,
    LLMSummarizer,
    SimpleSummarizer,
)

logger = logging.getLogger(__name__)


class HistoryManagerBuilder:
    """Fluent builder for HistoryManager configuration.

    Provides a chainable API for configuring HistoryManager instances
    with sensible defaults and type safety.

    Example:
        >>> from agent_framework.llm.provider import MockLLMProvider
        >>> llm = MockLLMProvider()
        >>> history = (HistoryManagerBuilder()
        ...     .with_llm_summarizer(llm)
        ...     .with_retention_window(15)
        ...     .with_max_tokens(8000)
        ...     .build())
    """

    def __init__(self):
        """Initialize builder with default values."""
        self._summarizer: Optional[HistorySummarizer] = None
        self._model_config: Optional[ModelConfig] = None
        self._system_prompt_tokens: int = 0
        self._tools_tokens: int = 0
        self._retention_window: int = 10
        self._buffer_tokens: int = 500
        self._max_tokens: Optional[int] = None
        self._auto_remove_old_todos: bool = True
        self._proactive_threshold: float = 0.8
        self._publish_callback: Optional[callable] = None
        self._compaction_strategy: Optional[CompactionStrategy] = None
        self._message_cleaners: Optional[list[MessageCleaner]] = None

    def with_summarizer(self, summarizer: HistorySummarizer) -> "HistoryManagerBuilder":
        """Set the summarizer to use for compaction.

        Args:
            summarizer: HistorySummarizer instance

        Returns:
            Self for chaining
        """
        self._summarizer = summarizer
        return self

    def with_simple_summarizer(self) -> "HistoryManagerBuilder":
        """Use SimpleSummarizer for compaction.

        Returns:
            Self for chaining
        """
        self._summarizer = SimpleSummarizer()
        return self

    def with_llm_summarizer(self, llm) -> "HistoryManagerBuilder":
        """Use LLMSummarizer for intelligent compaction.

        Args:
            llm: LLM provider instance

        Returns:
            Self for chaining
        """
        self._summarizer = LLMSummarizer(llm)
        return self

    def with_hybrid_summarizer(self, llm, threshold: int = 5) -> "HistoryManagerBuilder":
        """Use HybridSummarizer (LLM for large chunks, simple for small).

        Args:
            llm: LLM provider instance
            threshold: Minimum messages to use LLM (default: 5)

        Returns:
            Self for chaining
        """
        self._summarizer = HybridSummarizer(llm, threshold=threshold)
        return self

    def with_model_config(self, model_config: ModelConfig) -> "HistoryManagerBuilder":
        """Set model configuration for automatic token limit calculation.

        Args:
            model_config: ModelConfig instance

        Returns:
            Self for chaining
        """
        self._model_config = model_config
        return self

    def with_system_prompt_tokens(self, tokens: int) -> "HistoryManagerBuilder":
        """Set estimated tokens in system prompt.

        Args:
            tokens: Number of tokens

        Returns:
            Self for chaining
        """
        self._system_prompt_tokens = tokens
        return self

    def with_tools_tokens(self, tokens: int) -> "HistoryManagerBuilder":
        """Set estimated tokens in tool definitions.

        Args:
            tokens: Number of tokens

        Returns:
            Self for chaining
        """
        self._tools_tokens = tokens
        return self

    def with_retention_window(self, window: int) -> "HistoryManagerBuilder":
        """Set number of recent messages to preserve during compaction.

        Args:
            window: Number of messages (default: 10)

        Returns:
            Self for chaining
        """
        self._retention_window = window
        return self

    def with_buffer_tokens(self, tokens: int) -> "HistoryManagerBuilder":
        """Set safety buffer for token counting.

        Args:
            tokens: Number of buffer tokens (default: 500)

        Returns:
            Self for chaining
        """
        self._buffer_tokens = tokens
        return self

    def with_max_tokens(self, tokens: int) -> "HistoryManagerBuilder":
        """Set maximum tokens (overrides model config calculation).

        Args:
            tokens: Maximum number of tokens

        Returns:
            Self for chaining
        """
        self._max_tokens = tokens
        return self

    def with_todo_removal(self, enabled: bool = True) -> "HistoryManagerBuilder":
        """Enable or disable automatic TODO removal.

        Args:
            enabled: Whether to auto-remove old TODOs (default: True)

        Returns:
            Self for chaining
        """
        self._auto_remove_old_todos = enabled
        return self

    def with_proactive_threshold(self, threshold: float) -> "HistoryManagerBuilder":
        """Set proactive compaction threshold.

        Args:
            threshold: Fraction of max_tokens (0.0-1.0, default: 0.8)

        Returns:
            Self for chaining
        """
        self._proactive_threshold = threshold
        return self

    def with_publish_callback(self, callback: callable) -> "HistoryManagerBuilder":
        """Set callback for compaction notifications.

        Args:
            callback: Function to call on compaction events

        Returns:
            Self for chaining
        """
        self._publish_callback = callback
        return self

    def with_compaction_strategy(
        self, strategy: CompactionStrategy
    ) -> "HistoryManagerBuilder":
        """Set custom compaction strategy.

        Args:
            strategy: CompactionStrategy instance

        Returns:
            Self for chaining
        """
        self._compaction_strategy = strategy
        return self

    def with_selective_retention(self) -> "HistoryManagerBuilder":
        """Use SelectiveRetentionStrategy (anchor method).

        Returns:
            Self for chaining
        """
        self._compaction_strategy = SelectiveRetentionStrategy()
        return self

    def with_sliding_window(self) -> "HistoryManagerBuilder":
        """Use SlidingWindowStrategy (simple window).

        Returns:
            Self for chaining
        """
        self._compaction_strategy = SlidingWindowStrategy()
        return self

    def with_message_cleaners(
        self, cleaners: list[MessageCleaner]
    ) -> "HistoryManagerBuilder":
        """Set custom message cleaners.

        Args:
            cleaners: List of MessageCleaner instances

        Returns:
            Self for chaining
        """
        self._message_cleaners = cleaners
        return self

    def with_todo_cleaner(self) -> "HistoryManagerBuilder":
        """Add TODOCleaner to message cleaners.

        Returns:
            Self for chaining
        """
        if self._message_cleaners is None:
            self._message_cleaners = []
        self._message_cleaners.append(TODOCleaner())
        return self

    def with_duplicate_cleaner(self) -> "HistoryManagerBuilder":
        """Add DuplicateCleaner to message cleaners.

        Returns:
            Self for chaining
        """
        if self._message_cleaners is None:
            self._message_cleaners = []
        self._message_cleaners.append(DuplicateCleaner())
        return self

    def build(self):
        """Build the HistoryManager instance.

        Returns:
            Configured HistoryManager instance

        Raises:
            ValueError: If summarizer is not set
        """
        # Import here to avoid circular dependency
        from .history import HistoryManager

        if self._summarizer is None:
            raise ValueError(
                "Summarizer is required. Use with_simple_summarizer(), "
                "with_llm_summarizer(), or with_summarizer()."
            )

        return HistoryManager(
            summarizer=self._summarizer,
            model_config=self._model_config,
            system_prompt_tokens=self._system_prompt_tokens,
            tools_tokens=self._tools_tokens,
            retention_window=self._retention_window,
            buffer_tokens=self._buffer_tokens,
            max_tokens=self._max_tokens,
            auto_remove_old_todos=self._auto_remove_old_todos,
            proactive_threshold=self._proactive_threshold,
            publish_callback=self._publish_callback,
            compaction_strategy=self._compaction_strategy,
            message_cleaners=self._message_cleaners,
        )


class HistoryManagerPresets:
    """Preset configurations for common HistoryManager use cases.

    Provides factory methods for quickly creating HistoryManager instances
    with sensible defaults for different scenarios.
    """

    @staticmethod
    def minimal(max_tokens: int = 4000) -> "HistoryManagerBuilder":
        """Minimal configuration for testing or simple use cases.

        Args:
            max_tokens: Maximum tokens (default: 4000)

        Returns:
            Configured builder (call .build() to create instance)
        """
        return (
            HistoryManagerBuilder()
            .with_simple_summarizer()
            .with_max_tokens(max_tokens)
            .with_retention_window(5)
            .with_todo_removal(False)
        )

    @staticmethod
    def development(llm, max_tokens: int = 8000) -> "HistoryManagerBuilder":
        """Development configuration with LLM summarization.

        Args:
            llm: LLM provider instance
            max_tokens: Maximum tokens (default: 8000)

        Returns:
            Configured builder (call .build() to create instance)
        """
        return (
            HistoryManagerBuilder()
            .with_llm_summarizer(llm)
            .with_max_tokens(max_tokens)
            .with_retention_window(10)
            .with_todo_removal(True)
            .with_proactive_threshold(0.8)
        )

    @staticmethod
    def production(llm, model_config: ModelConfig) -> "HistoryManagerBuilder":
        """Production configuration with all optimizations.

        Args:
            llm: LLM provider instance
            model_config: Model configuration for automatic limits

        Returns:
            Configured builder (call .build() to create instance)
        """
        return (
            HistoryManagerBuilder()
            .with_hybrid_summarizer(llm, threshold=5)
            .with_model_config(model_config)
            .with_retention_window(15)
            .with_todo_removal(True)
            .with_duplicate_cleaner()
            .with_proactive_threshold(0.75)
            .with_selective_retention()
        )

    @staticmethod
    def chat(llm, max_tokens: int = 4000) -> "HistoryManagerBuilder":
        """Chat-optimized configuration with sliding window.

        Args:
            llm: LLM provider instance
            max_tokens: Maximum tokens (default: 4000)

        Returns:
            Configured builder (call .build() to create instance)
        """
        return (
            HistoryManagerBuilder()
            .with_simple_summarizer()
            .with_max_tokens(max_tokens)
            .with_retention_window(20)
            .with_sliding_window()
            .with_todo_removal(False)
            .with_duplicate_cleaner()
        )

    @staticmethod
    def long_conversation(llm, max_tokens: int = 16000) -> "HistoryManagerBuilder":
        """Long conversation configuration with aggressive cleaning.

        Args:
            llm: LLM provider instance
            max_tokens: Maximum tokens (default: 16000)

        Returns:
            Configured builder (call .build() to create instance)
        """
        return (
            HistoryManagerBuilder()
            .with_hybrid_summarizer(llm, threshold=10)
            .with_max_tokens(max_tokens)
            .with_retention_window(25)
            .with_todo_removal(True)
            .with_duplicate_cleaner()
            .with_proactive_threshold(0.7)
        )
