"""
Tests for LLM format caching (Task 2.4).

Tests verify:
1. Cache is built on first to_llm_format() call
2. Cache is returned on subsequent calls (no rebuild)
3. Cache is invalidated on add()
4. Cache is invalidated on add_async()
5. Cache is invalidated on compact()
6. Cache is invalidated on compact_async()
7. Cache is invalidated on clear()
8. Cache is invalidated on TODO removal
9. Performance improvement is measurable
"""
import unittest
import asyncio
import time
from agent_framework.memory.history import HistoryManager
from agent_framework.memory.summarizer import SimpleSummarizer
from agent_framework.messages.types import (
    SystemMessage,
    UserMessage,
    ToolCallMessage,
    ToolResultObservation,
    ToolCall
)


class TestLLMFormatCaching(unittest.TestCase):
    """Test LLM format caching functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.summarizer = SimpleSummarizer()

    def test_cache_built_on_first_call(self):
        """Test that cache is built on first to_llm_format() call."""
        history = HistoryManager(
            summarizer=self.summarizer,
            max_tokens=5000,
            retention_window=10
        )

        # Add messages
        history.add(UserMessage(content="Hello", session_id="test", sequence=0))
        history.add(UserMessage(content="World", session_id="test", sequence=1))

        # Cache should be None initially
        self.assertIsNone(history._llm_format_cache)

        # Call to_llm_format
        result = history.to_llm_format()

        # Cache should now be populated
        self.assertIsNotNone(history._llm_format_cache)
        self.assertEqual(result, history._llm_format_cache)

    def test_cache_returned_on_subsequent_calls(self):
        """Test that cache is returned on subsequent calls (no rebuild)."""
        history = HistoryManager(
            summarizer=self.summarizer,
            max_tokens=5000,
            retention_window=10
        )

        # Add messages
        for i in range(10):
            history.add(UserMessage(
                content=f"Message {i}",
                session_id="test",
                sequence=i
            ))

        # First call builds cache
        result1 = history.to_llm_format()
        cached = history._llm_format_cache

        # Second call should return exact same object (from cache)
        result2 = history.to_llm_format()

        # Should be the same object (not a copy)
        self.assertIs(result2, cached)
        self.assertEqual(result1, result2)

    def test_cache_invalidated_on_add(self):
        """Test that cache is invalidated when add() is called."""
        history = HistoryManager(
            summarizer=self.summarizer,
            max_tokens=5000,
            retention_window=10
        )

        # Add messages and build cache
        history.add(UserMessage(content="Hello", session_id="test", sequence=0))
        history.to_llm_format()
        self.assertIsNotNone(history._llm_format_cache)

        # Add another message - should invalidate cache
        history.add(UserMessage(content="World", session_id="test", sequence=1))
        self.assertIsNone(history._llm_format_cache,
                         "Cache should be invalidated after add()")

    def test_cache_invalidated_on_add_async(self):
        """Test that cache is invalidated when add_async() is called."""
        async def run_test():
            history = HistoryManager(
                summarizer=self.summarizer,
                max_tokens=5000,
                retention_window=10
            )

            # Add messages and build cache
            await history.add_async(UserMessage(content="Hello", session_id="test", sequence=0))
            history.to_llm_format()
            self.assertIsNotNone(history._llm_format_cache)

            # Add another message asynchronously - should invalidate cache
            await history.add_async(UserMessage(content="World", session_id="test", sequence=1))
            self.assertIsNone(history._llm_format_cache,
                             "Cache should be invalidated after add_async()")

        asyncio.run(run_test())

    def test_cache_invalidated_on_compact(self):
        """Test that cache is invalidated after compaction."""
        history = HistoryManager(
            summarizer=self.summarizer,
            max_tokens=50000,  # High limit to avoid auto-compaction during add()
            retention_window=3,
            proactive_threshold=1.0  # Disable proactive compaction for this test
        )

        # Add many messages (won't trigger auto-compaction due to high max_tokens)
        for i in range(20):
            history.add(UserMessage(
                content=f"Message {i} " * 15,
                session_id="test",
                sequence=i
            ))

        # Build cache
        history.to_llm_format()
        self.assertIsNotNone(history._llm_format_cache)

        # Explicitly compact (should invalidate cache)
        history.compact()

        # Cache should be invalidated
        self.assertIsNone(history._llm_format_cache,
                         "Cache should be invalidated after compact()")

    def test_cache_invalidated_on_compact_async(self):
        """Test that cache is invalidated after async compaction."""
        async def run_test():
            history = HistoryManager(
                summarizer=self.summarizer,
                max_tokens=200,
                retention_window=3
            )

            # Add many messages
            for i in range(20):
                history.add(UserMessage(
                    content=f"Message {i} " * 15,
                    session_id="test",
                    sequence=i
                ))

            # Build cache
            history.to_llm_format()
            self.assertIsNotNone(history._llm_format_cache)

            # Compact asynchronously
            await history.compact_async()

            # Cache should be invalidated
            self.assertIsNone(history._llm_format_cache,
                             "Cache should be invalidated after compact_async()")

        asyncio.run(run_test())

    def test_cache_invalidated_on_clear(self):
        """Test that cache is reset when history is cleared."""
        history = HistoryManager(
            summarizer=self.summarizer,
            max_tokens=5000,
            retention_window=10
        )

        # Add messages and build cache
        for i in range(10):
            history.add(UserMessage(
                content=f"Message {i}",
                session_id="test",
                sequence=i
            ))
        history.to_llm_format()
        self.assertIsNotNone(history._llm_format_cache)

        # Clear history
        history.clear()

        # Cache should be reset to None
        self.assertIsNone(history._llm_format_cache,
                         "Cache should be reset after clear()")

    def test_cache_invalidated_on_todo_removal(self):
        """Test that cache is invalidated when TODOs are removed."""
        history = HistoryManager(
            summarizer=self.summarizer,
            max_tokens=5000,
            retention_window=5,
            auto_remove_old_todos=True
        )

        # Add first TODO
        history.add(ToolCallMessage(
            tool_calls=[
                ToolCall(id="todo_1", tool_name="todo_write", arguments={"todos": ["Task 1"]})
            ],
            session_id="test",
            sequence=0
        ))
        history.add(ToolResultObservation(
            call_id="todo_1",
            content="TODO updated",
            session_id="test",
            sequence=1
        ))

        # Add many messages to push TODO outside retention window
        for i in range(10):
            history.add(UserMessage(
                content=f"Message {i}",
                session_id="test",
                sequence=i + 2
            ))

        # Build cache
        history.to_llm_format()
        self.assertIsNotNone(history._llm_format_cache)

        # Add second TODO (should trigger removal of first and invalidate cache)
        history.add(ToolCallMessage(
            tool_calls=[
                ToolCall(id="todo_2", tool_name="todo_write", arguments={"todos": ["Task 2"]})
            ],
            session_id="test",
            sequence=100
        ))

        # Cache should have been invalidated
        self.assertIsNone(history._llm_format_cache,
                         "Cache should be invalidated when TODOs are removed")

    def test_cache_accuracy(self):
        """Test that cached result is identical to freshly built result."""
        history = HistoryManager(
            summarizer=self.summarizer,
            max_tokens=5000,
            retention_window=10
        )

        # Add various message types
        history.add(SystemMessage(content="System", session_id="test", sequence=0))
        history.add(UserMessage(content="User", session_id="test", sequence=1))
        history.add(ToolCallMessage(
            tool_calls=[
                ToolCall(id="call_1", tool_name="read_file", arguments={"path": "/test"})
            ],
            session_id="test",
            sequence=2
        ))
        history.add(ToolResultObservation(
            call_id="call_1",
            content="File content",
            session_id="test",
            sequence=3
        ))

        # Get first result (builds cache)
        result1 = history.to_llm_format()

        # Invalidate cache and rebuild
        history._llm_format_cache = None
        result2 = history.to_llm_format()

        # Results should be identical
        self.assertEqual(result1, result2)

    def test_format_caching_performance(self):
        """Test that caching provides performance improvement."""
        history = HistoryManager(
            summarizer=self.summarizer,
            max_tokens=50000,
            retention_window=10
        )

        # Add many messages with complex content
        for i in range(200):
            history.add(UserMessage(
                content=f"Message {i} with some content " * 10,
                session_id="test",
                sequence=i
            ))

        # Time first call (builds cache)
        start_build = time.time()
        result1 = history.to_llm_format()
        elapsed_build = time.time() - start_build

        # Time subsequent calls (from cache)
        total_cached_time = 0
        for _ in range(100):
            start_cached = time.time()
            result_cached = history.to_llm_format()
            total_cached_time += time.time() - start_cached

        avg_cached_time = total_cached_time / 100

        # Cached calls should be significantly faster
        speedup = elapsed_build / avg_cached_time if avg_cached_time > 0 else 0

        print(f"\nLLM Format Caching Performance (200 messages):")
        print(f"  Build cache: {elapsed_build:.6f}s")
        print(f"  Cached access (avg of 100): {avg_cached_time:.6f}s")
        print(f"  Speedup: {speedup:.0f}x")

        # Cached access should be at least 10x faster (typically 100-1000x)
        self.assertGreater(speedup, 10.0,
                          f"Expected at least 10x speedup, got {speedup:.1f}x")

        # Verify correctness
        self.assertEqual(result1, result_cached)


if __name__ == '__main__':
    unittest.main(verbosity=2)
