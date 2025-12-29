"""
History Manager with Selective Retention compaction strategy.
"""
import asyncio
import json
import logging
import time
from typing import Any, Optional

from ..llm.model_config import ModelConfig
from ..messages.types import (
    AgentFinishedMessage,
    BaseMessage,
    BatchToolResultObservation,
    CompactionCompleteMessage,
    CompactionStartedMessage,
    EnvironmentMessage,
    LLMRespondMessage,
    ProjectContextMessage,
    SystemMessage,
    ToolCallMessage,
    ToolResultObservation,
    UserMessage,
)
from .compaction_strategy import CompactionStrategy, SelectiveRetentionStrategy
from .message_cleaner import MessageCleaner, TODOCleaner
from .message_formatter import MessageFormatter
from .summarizer import HistorySummarizer

logger = logging.getLogger(__name__)

class HistoryManager:
    """
    Manages conversation history with token-aware compaction.
    
    Strategy: Selective Retention (Anchor Method)
    1. Always keep System Prompt (usually first message)
    2. Always keep Initial User Request (Goal)
    3. Keep Last N messages (Working Context)
    4. Summarize or drop the middle
    """

    def __init__(
        self,
        summarizer: HistorySummarizer,
        model_config: ModelConfig | None = None,
        system_prompt_tokens: int = 0,
        tools_tokens: int = 0,
        retention_window: int = 10,
        buffer_tokens: int = 500,
        max_tokens: int | None = None,
        auto_remove_old_todos: bool = True,
        proactive_threshold: float = 0.8,
        publish_callback: Optional[callable] = None,
        compaction_strategy: Optional[CompactionStrategy] = None,
        message_cleaners: Optional[list[MessageCleaner]] = None
    ):
        """
        Initialize HistoryManager with model-aware token limits.

        Args:
            summarizer: HistorySummarizer instance (REQUIRED).
            model_config: ModelConfig for the LLM being used. If provided,
                         max_tokens is calculated automatically.
            system_prompt_tokens: Estimated tokens in system prompt.
            tools_tokens: Estimated tokens in tool definitions.
            retention_window: Number of recent messages to keep.
            buffer_tokens: Safety buffer for token counting errors.
            max_tokens: Override calculated max_tokens if provided.
                       If both model_config and max_tokens are None,
                       defaults to 4000 (conservative).
            auto_remove_old_todos: If True, automatically remove old TODO messages
                                  when new TODO messages are added. Reduces token
                                  usage by keeping only the current TODO state.
                                  Default: True.
            proactive_threshold: Fraction of max_tokens (0.0-1.0) at which to trigger
                               proactive compaction. Default: 0.8 (80%).
                               Set to 1.0 to disable proactive compaction.
            publish_callback: Optional callback function for publishing notification messages.
                            Called with (message) when compaction events occur.
                            Default: None (no notifications).
            compaction_strategy: Strategy for determining which messages to preserve.
                               If None, defaults to SelectiveRetentionStrategy.
                               Default: None (uses SelectiveRetentionStrategy).
            message_cleaners: Optional list of MessageCleaner instances to apply.
                            If None and auto_remove_old_todos is True, uses TODOCleaner.
                            If empty list, no cleaners are applied.
                            Default: None (auto-configure based on auto_remove_old_todos).
        """
        if summarizer is None:
            raise ValueError(
                "summarizer is required. Use LLMSummarizer(llm) for intelligent summaries "
                "or SimpleSummarizer() for basic summaries."
            )

        self.summarizer = summarizer
        self.retention_window = retention_window
        self.auto_remove_old_todos = auto_remove_old_todos
        self.proactive_threshold = proactive_threshold
        self.publish_callback = publish_callback  # Task 2.5: Compaction Notifications

        # Compaction strategy (Task 3.1.2: Extract CompactionStrategy)
        self.compaction_strategy = compaction_strategy or SelectiveRetentionStrategy()

        # Message cleaners (Task 3.1.3: Extract MessageCleaner)
        if message_cleaners is None:
            # Auto-configure based on auto_remove_old_todos for backward compatibility
            self.message_cleaners = [TODOCleaner()] if auto_remove_old_todos else []
        else:
            self.message_cleaners = message_cleaners

        # Calculate max tokens based on model config or use override
        if max_tokens is not None:
            self.max_tokens = max_tokens
            logger.info(f"HistoryManager using explicit max_tokens={max_tokens}")
        elif model_config is not None:
            self.max_tokens = model_config.get_available_context(
                system_prompt_tokens=system_prompt_tokens,
                tools_tokens=tools_tokens,
                buffer_tokens=buffer_tokens
            )
            logger.info(
                f"HistoryManager calculated max_tokens={self.max_tokens} "
                f"(model={model_config.model_name}, context={model_config.context_window}, "
                f"system={system_prompt_tokens}, tools={tools_tokens}, buffer={buffer_tokens})"
            )
        else:
            self.max_tokens = 4000
            logger.warning(
                "No model_config or max_tokens provided, using default max_tokens=4000. "
                "Consider providing model_config for optimal token management."
            )

        self._messages: list[BaseMessage] = []
        self.summary_message: SystemMessage | None = None

        # Async compaction support
        self._compaction_lock: Optional[asyncio.Lock] = None
        self._compaction_task: Optional[asyncio.Task] = None

        # Token caching for O(1) performance (Task 2.3)
        self._token_cache: int = 0
        self._cache_valid: bool = True

        # LLM format caching to avoid rebuilding on every call (Task 2.4)
        self._llm_format_cache: Optional[list[dict[str, Any]]] = None

        # Message formatter for converting to LLM format (Task 3.1)
        self._formatter = MessageFormatter()

    @property
    def compaction_lock(self) -> asyncio.Lock:
        """Lazy initialization of compaction lock."""
        if self._compaction_lock is None:
            try:
                self._compaction_lock = asyncio.Lock()
            except RuntimeError:
                # No event loop yet, will be created when needed
                pass
        return self._compaction_lock

    def add(self, message: BaseMessage) -> None:
        """Add a message to history and trigger compaction if needed."""
        self._messages.append(message)

        # Apply message cleaners (Task 3.1.3: MessageCleaner)
        if self.message_cleaners:
            messages_before = len(self._messages)
            for cleaner in self.message_cleaners:
                self._messages = cleaner.clean(self._messages, self.retention_window)

            # Invalidate caches if messages were removed
            if len(self._messages) < messages_before:
                self._cache_valid = False
                self._llm_format_cache = None

        # Invalidate LLM format cache (messages changed)
        self._llm_format_cache = None

        # Incremental token update (O(1) instead of O(n))
        if self._cache_valid:
            msg_tokens = self._count_message_tokens(message)
            self._token_cache += msg_tokens
        else:
            # Cache was invalidated, will recalculate on next get_token_estimate()
            pass

        # Check compaction with proactive threshold
        current_tokens = self.get_token_estimate()
        utilization = current_tokens / self.max_tokens if self.max_tokens > 0 else 0

        logger.debug(
            f"History: {len(self._messages)} messages, "
            f"{current_tokens}/{self.max_tokens} tokens ({utilization:.1%})"
        )

        # Proactive compaction at threshold (default 80%)
        if utilization >= self.proactive_threshold:
            logger.info(
                f"Triggering proactive compaction at {utilization:.1%} "
                f"(threshold={self.proactive_threshold:.1%})"
            )
            try:
                self.schedule_compaction_background()
            except RuntimeError:
                # No event loop - use sync compaction
                self.compact()

        # Emergency compaction at 100% (if proactive failed or was disabled)
        elif utilization >= 1.0:
            logger.warning(
                f"Emergency compaction at {utilization:.1%}! "
                f"(proactive threshold was {self.proactive_threshold:.1%})"
            )
            self.compact()  # Block until complete in emergency

    def get_messages(self) -> list[BaseMessage]:
        """Get the current effective list of messages."""
        return self.messages

    @property
    def messages(self) -> list[BaseMessage]:
        """Backward-compatible property to access internal messages list."""
        return self._messages

    def get_token_estimate(self) -> int:
        """
        Get current token count (with caching for O(1) performance).

        Uses cached value if valid, otherwise recalculates.
        Cache is invalidated on compaction or TODO removal.
        """
        if not self._cache_valid:
            # Recalculate tokens (O(n))
            self._token_cache = self._recalculate_tokens()
            self._cache_valid = True

        return self._token_cache

    def _recalculate_tokens(self) -> int:
        """
        Recalculate total tokens from scratch (O(n)).

        Called when cache is invalidated (after compaction or TODO removal).
        """
        total_chars = 0
        for msg in self._messages:
            # Estimate based on content and other fields
            content = ""
            if hasattr(msg, 'content') and msg.content:
                content += str(msg.content)
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                content += str(msg.tool_calls)

            total_chars += len(content)

        return total_chars // 4

    def _count_message_tokens(self, message: BaseMessage) -> int:
        """
        Count tokens in a single message (for incremental cache updates).

        Args:
            message: Message to count tokens for

        Returns:
            Estimated token count for this message
        """
        content = ""
        if hasattr(message, 'content') and message.content:
            content += str(message.content)
        if hasattr(message, 'tool_calls') and message.tool_calls:
            content += str(message.tool_calls)

        return len(content) // 4

    def clear(self) -> None:
        """Clear all messages from history."""
        self._messages.clear()
        self.summary_message = None

        # Reset caches
        self._token_cache = 0
        self._cache_valid = True
        self._llm_format_cache = None

        logger.info("History cleared - all messages removed")

    def compact(self) -> None:
        """
        Execute compaction strategy.
        
        Preserves:
        - System Message (if at index 0)
        - First User Message (Goal)
        - Last N messages
        
        Summarizes/Drops:
        - The middle chunk
        """
        if len(self._messages) <= self.retention_window + 2:
            return

        # Capture state before compaction (Task 2.5: Compaction Notifications)
        messages_before = len(self._messages)
        tokens_before = self.get_token_estimate()
        utilization = tokens_before / self.max_tokens if self.max_tokens > 0 else 0.0
        start_time = time.time()

        # Publish compaction started notification
        if self.publish_callback:
            started_msg = CompactionStartedMessage(
                session_id=self._messages[0].session_id if self._messages else "unknown",
                sequence=0,
                messages_count=messages_before,
                tokens_before=tokens_before,
                utilization=utilization
            )
            self.publish_callback(started_msg)

        logger.info("Compacting history (current size: %d, tokens: %d)",
                    messages_before, tokens_before)

        # Use compaction strategy to analyze which messages to preserve (Task 3.1.2)
        analysis = self.compaction_strategy.analyze(self._messages, self.retention_window)

        if not analysis.middle_chunk:
            return

        # 4. Summarize Middle using the summarizer
        summary_text = self.summarizer.summarize(analysis.middle_chunk)
        logger.info(f"Generated summary: {summary_text[:100]}...")

        # Create summary message
        summary_msg = SystemMessage(
            content=summary_text,
            session_id=self._messages[0].session_id if self._messages else "unknown",
            sequence=0
        )

        # Reconstruct messages
        self._messages = analysis.preserved_head + [summary_msg] + analysis.preserved_tail

        # Invalidate caches (structure changed)
        self._cache_valid = False
        self._llm_format_cache = None

        # Publish compaction complete notification (Task 2.5)
        messages_after = len(self._messages)
        tokens_after = self.get_token_estimate()
        time_elapsed = time.time() - start_time

        if self.publish_callback:
            complete_msg = CompactionCompleteMessage(
                session_id=self._messages[0].session_id if self._messages else "unknown",
                sequence=0,
                messages_before=messages_before,
                messages_after=messages_after,
                tokens_before=tokens_before,
                tokens_after=tokens_after,
                time_elapsed=time_elapsed,
                messages_compacted=messages_before - messages_after,
                tokens_saved=tokens_before - tokens_after
            )
            self.publish_callback(complete_msg)

        logger.info("Compaction complete. New size: %d", messages_after)

    async def compact_async(self) -> None:
        """
        Async version of compaction (non-blocking).

        Uses async summarization to avoid blocking the event loop.
        This method should be preferred over compact() in async contexts.
        """
        if len(self._messages) <= self.retention_window + 2:
            return

        # Ensure we have a lock
        if self.compaction_lock is None:
            logger.warning("No event loop available for async compaction, falling back to sync")
            self.compact()
            return

        async with self.compaction_lock:
            # Capture state before compaction (Task 2.5: Compaction Notifications)
            messages_before = len(self._messages)
            tokens_before = self.get_token_estimate()
            utilization = tokens_before / self.max_tokens if self.max_tokens > 0 else 0.0
            start_time = time.time()

            # Publish compaction started notification
            if self.publish_callback:
                started_msg = CompactionStartedMessage(
                    session_id=self._messages[0].session_id if self._messages else "unknown",
                    sequence=0,
                    messages_count=messages_before,
                    tokens_before=tokens_before,
                    utilization=utilization
                )
                self.publish_callback(started_msg)

            logger.info("Starting async compaction (current size: %d, tokens: %d)",
                       messages_before, tokens_before)

            # Use compaction strategy to analyze which messages to preserve (Task 3.1.2)
            analysis = self.compaction_strategy.analyze(self._messages, self.retention_window)

            if not analysis.middle_chunk:
                return

            # 4. Summarize Middle using async summarizer (non-blocking!)
            try:
                summary_text = await self.summarizer.summarize_async(analysis.middle_chunk)
                logger.info(f"Generated async summary: {summary_text[:100]}...")
            except Exception as e:
                logger.error(f"Async summarization failed: {e}. Using fallback.")
                from .summarizer import SimpleSummarizer
                summary_text = SimpleSummarizer().summarize(analysis.middle_chunk)

            # Create summary message
            summary_msg = SystemMessage(
                content=summary_text,
                session_id=self._messages[0].session_id if self._messages else "unknown",
                sequence=0
            )

            # Reconstruct messages
            self._messages = analysis.preserved_head + [summary_msg] + analysis.preserved_tail

            # Invalidate caches (structure changed)
            self._cache_valid = False
            self._llm_format_cache = None

            # Publish compaction complete notification (Task 2.5)
            messages_after = len(self._messages)
            tokens_after = self.get_token_estimate()
            time_elapsed = time.time() - start_time

            if self.publish_callback:
                complete_msg = CompactionCompleteMessage(
                    session_id=self._messages[0].session_id if self._messages else "unknown",
                    sequence=0,
                    messages_before=messages_before,
                    messages_after=messages_after,
                    tokens_before=tokens_before,
                    tokens_after=tokens_after,
                    time_elapsed=time_elapsed,
                    messages_compacted=messages_before - messages_after,
                    tokens_saved=tokens_before - tokens_after
                )
                self.publish_callback(complete_msg)

            logger.info("Async compaction complete. New size: %d", messages_after)

    def schedule_compaction_background(self) -> None:
        """
        Schedule compaction to run in background (non-blocking).

        This allows add() to return immediately while compaction happens asynchronously.
        """
        try:
            # Check if we already have a compaction running
            if self._compaction_task is not None and not self._compaction_task.done():
                logger.debug("Compaction already in progress, skipping")
                return

            # Schedule compaction as background task
            self._compaction_task = asyncio.create_task(self.compact_async())
            logger.debug("Background compaction scheduled")

        except RuntimeError as e:
            # No event loop available - fall back to sync compaction
            logger.debug(f"No event loop for background compaction: {e}. Using sync.")
            self.compact()

    async def add_async(self, message: BaseMessage) -> None:
        """
        Async version of add (awaits compaction if needed).

        Use this in async contexts when you want to wait for compaction to complete.

        Args:
            message: Message to add to history
        """
        self._messages.append(message)

        # Apply message cleaners (Task 3.1.3: MessageCleaner)
        if self.message_cleaners:
            messages_before = len(self._messages)
            for cleaner in self.message_cleaners:
                self._messages = cleaner.clean(self._messages, self.retention_window)

            # Invalidate caches if messages were removed
            if len(self._messages) < messages_before:
                self._cache_valid = False
                self._llm_format_cache = None

        # Invalidate LLM format cache (messages changed)
        self._llm_format_cache = None

        # Incremental token update (O(1) instead of O(n))
        if self._cache_valid:
            msg_tokens = self._count_message_tokens(message)
            self._token_cache += msg_tokens

        # Check compaction with proactive threshold
        current_tokens = self.get_token_estimate()
        utilization = current_tokens / self.max_tokens if self.max_tokens > 0 else 0

        # Proactive compaction at threshold (default 80%)
        if utilization >= self.proactive_threshold:
            logger.info(
                f"Triggering proactive async compaction at {utilization:.1%} "
                f"(threshold={self.proactive_threshold:.1%})"
            )
            await self.compact_async()

        # Emergency compaction at 100%
        elif utilization >= 1.0:
            logger.warning(
                f"Emergency async compaction at {utilization:.1%}!"
            )
            await self.compact_async()

    def to_llm_format(self) -> list[dict[str, Any]]:
        """Convert to LLM format (with caching for performance).

        Delegates to MessageFormatter for the conversion logic (Task 3.1).
        """
        # Return cached version if available (Task 2.4: LLM Format Caching)
        if self._llm_format_cache is not None:
            return self._llm_format_cache

        # Delegate to MessageFormatter (Task 3.1: Extract MessageFormatter)
        llm_messages = self._formatter.to_llm_format(self._messages)

        # Cache the result before returning (Task 2.4: LLM Format Caching)
        self._llm_format_cache = llm_messages
        return llm_messages
