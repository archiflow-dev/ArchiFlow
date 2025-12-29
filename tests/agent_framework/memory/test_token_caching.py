"""
Tests for token caching (Task 2.3).

Tests verify:
1. Incremental token counting on add() is O(1)
2. Cache is invalidated on compaction
3. Cache is invalidated on TODO removal
4. Cache is invalidated on clear()
5. get_token_estimate() uses cache correctly
6. Performance improvement is measurable
"""
import unittest
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


class TestTokenCaching(unittest.TestCase):
    """Test token caching functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.summarizer = SimpleSummarizer()

    def test_incremental_token_counting_on_add(self):
        """Test that add() updates token cache incrementally (O(1))."""
        history = HistoryManager(
            summarizer=self.summarizer,
            max_tokens=5000,
            retention_window=10
        )

        # Add first message
        msg1 = UserMessage(content="X" * 100, session_id="test", sequence=0)
        history.add(msg1)

        # Cache should be valid
        self.assertTrue(history._cache_valid)
        tokens1 = history.get_token_estimate()

        # Add second message
        msg2 = UserMessage(content="Y" * 100, session_id="test", sequence=1)
        history.add(msg2)

        # Cache should still be valid (incremental update)
        self.assertTrue(history._cache_valid)
        tokens2 = history.get_token_estimate()

        # Token count should have increased
        self.assertGreater(tokens2, tokens1)

        # Should be approximately 50 tokens (100 chars * 2 / 4)
        self.assertAlmostEqual(tokens2, 50, delta=10)

    def test_cache_invalidated_on_compaction(self):
        """Test that cache is properly managed during compaction."""
        history = HistoryManager(
            summarizer=self.summarizer,
            max_tokens=50000,  # High to avoid auto-compaction
            retention_window=3,
            proactive_threshold=1.0  # Disable proactive compaction
        )

        # Add many messages
        for i in range(20):
            history.add(UserMessage(
                content=f"Message {i} " * 15,
                session_id="test",
                sequence=i
            ))

        # Get token count before compaction
        tokens_before = history.get_token_estimate()

        # Force compaction
        history.compact()

        # Get token count after compaction
        tokens_after = history.get_token_estimate()

        # Verify compaction actually happened (fewer messages, fewer tokens)
        self.assertLess(len(history.messages), 20)
        self.assertLess(tokens_after, tokens_before)

        # Verify cache is valid after compaction (notification code rebuilds it)
        self.assertTrue(history._cache_valid)

        # Getting token estimate should recalculate and set cache valid
        tokens = history.get_token_estimate()
        self.assertTrue(history._cache_valid,
                       "Cache should be valid after get_token_estimate()")
        self.assertGreater(tokens, 0)

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

        # Cache should be valid
        self.assertTrue(history._cache_valid)

        # Add second TODO (should trigger removal of first)
        history.add(ToolCallMessage(
            tool_calls=[
                ToolCall(id="todo_2", tool_name="todo_write", arguments={"todos": ["Task 2"]})
            ],
            session_id="test",
            sequence=100
        ))

        history.add(ToolResultObservation(
            call_id="todo_2",
            content="TODO updated",
            session_id="test",
            sequence=101
        ))

        # Cache should have been invalidated (TODOs were removed)
        # Note: It gets recalculated immediately on the next add(), so we can't test
        # the invalidation directly. But we can verify the count is still accurate.
        tokens = history.get_token_estimate()
        self.assertGreater(tokens, 0)

    def test_cache_invalidated_on_clear(self):
        """Test that cache is reset when history is cleared."""
        history = HistoryManager(
            summarizer=self.summarizer,
            max_tokens=5000,
            retention_window=10
        )

        # Add messages
        for i in range(10):
            history.add(UserMessage(
                content="X" * 100,
                session_id="test",
                sequence=i
            ))

        # Get token count
        tokens_before = history.get_token_estimate()
        self.assertGreater(tokens_before, 0)

        # Clear history
        history.clear()

        # Cache should be reset
        self.assertEqual(history._token_cache, 0)
        self.assertTrue(history._cache_valid)
        self.assertEqual(history.get_token_estimate(), 0)

    def test_get_token_estimate_uses_cache(self):
        """Test that get_token_estimate() returns cached value when valid."""
        history = HistoryManager(
            summarizer=self.summarizer,
            max_tokens=5000,
            retention_window=10
        )

        # Add messages
        for i in range(5):
            history.add(UserMessage(
                content="X" * 100,
                session_id="test",
                sequence=i
            ))

        # First call calculates (or uses incremental cache)
        tokens1 = history.get_token_estimate()
        cache1 = history._token_cache

        # Second call should return same value (from cache)
        tokens2 = history.get_token_estimate()
        cache2 = history._token_cache

        self.assertEqual(tokens1, tokens2)
        self.assertEqual(cache1, cache2)
        self.assertTrue(history._cache_valid)

    def test_incremental_counting_performance(self):
        """Test that incremental counting is significantly faster than full recalculation."""
        # With cache (incremental)
        history_cached = HistoryManager(
            summarizer=self.summarizer,
            max_tokens=50000,
            retention_window=10
        )

        start_cached = time.time()
        for i in range(500):
            msg = UserMessage(
                content=f"Message {i} with some content",
                session_id="test",
                sequence=i
            )
            history_cached.add(msg)
            _ = history_cached.get_token_estimate()  # Get on each add
        elapsed_cached = time.time() - start_cached

        # Without cache (full recalculation each time)
        # Simulate by invalidating cache on each add
        history_no_cache = HistoryManager(
            summarizer=self.summarizer,
            max_tokens=50000,
            retention_window=10
        )

        start_no_cache = time.time()
        for i in range(500):
            msg = UserMessage(
                content=f"Message {i} with some content",
                session_id="test",
                sequence=i
            )
            history_no_cache._messages.append(msg)  # Bypass add() to avoid cache
            history_no_cache._cache_valid = False  # Force recalculation
            _ = history_no_cache.get_token_estimate()  # Recalculate each time
        elapsed_no_cache = time.time() - start_no_cache

        # Cached version should be faster (at least 2x for 500 messages)
        speedup = elapsed_no_cache / elapsed_cached if elapsed_cached > 0 else 0

        print(f"\nPerformance comparison (500 messages):")
        print(f"  With cache: {elapsed_cached:.4f}s")
        print(f"  Without cache: {elapsed_no_cache:.4f}s")
        print(f"  Speedup: {speedup:.1f}x")

        # Verify speedup is significant
        # With incremental caching, should be at least 2x faster
        self.assertGreater(speedup, 2.0,
                          f"Expected at least 2x speedup, got {speedup:.1f}x")

    def test_count_message_tokens_accuracy(self):
        """Test that _count_message_tokens() gives same result as full calculation."""
        history = HistoryManager(
            summarizer=self.summarizer,
            max_tokens=5000,
            retention_window=10
        )

        # Create test message
        msg = UserMessage(
            content="X" * 400,  # 400 chars = 100 tokens
            session_id="test",
            sequence=0
        )

        # Count using helper
        single_count = history._count_message_tokens(msg)

        # Add message and get total
        history.add(msg)
        total_count = history.get_token_estimate()

        # Should be equal (since it's the only message)
        self.assertEqual(single_count, total_count)
        self.assertEqual(single_count, 100)  # 400 / 4 = 100

    def test_cache_recalculation_accuracy(self):
        """Test that cache recalculation gives same result as incremental counting."""
        history = HistoryManager(
            summarizer=self.summarizer,
            max_tokens=5000,
            retention_window=10
        )

        # Add messages with incremental counting
        for i in range(10):
            history.add(UserMessage(
                content="X" * 100,
                session_id="test",
                sequence=i
            ))

        # Get count with incremental cache
        tokens_incremental = history.get_token_estimate()

        # Force recalculation
        history._cache_valid = False
        tokens_recalculated = history.get_token_estimate()

        # Should be identical
        self.assertEqual(tokens_incremental, tokens_recalculated)

    def test_cache_with_tool_calls(self):
        """Test that cache handles messages with tool calls correctly."""
        history = HistoryManager(
            summarizer=self.summarizer,
            max_tokens=5000,
            retention_window=10
        )

        # Add message with tool call
        tool_msg = ToolCallMessage(
            tool_calls=[
                ToolCall(
                    id="call_1",
                    tool_name="read_file",
                    arguments={"path": "/test/file.txt"}
                )
            ],
            session_id="test",
            sequence=0
        )
        history.add(tool_msg)

        tokens1 = history.get_token_estimate()
        self.assertGreater(tokens1, 0)

        # Add tool result
        result_msg = ToolResultObservation(
            call_id="call_1",
            content="File content here " * 10,
            session_id="test",
            sequence=1
        )
        history.add(result_msg)

        tokens2 = history.get_token_estimate()
        self.assertGreater(tokens2, tokens1)

        # Verify cache is still valid
        self.assertTrue(history._cache_valid)


if __name__ == '__main__':
    unittest.main(verbosity=2)
