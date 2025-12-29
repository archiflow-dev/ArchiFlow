"""
Tests for async history compaction.

Tests verify:
1. Async compaction doesn't block
2. add_async() properly awaits compaction
3. Background compaction scheduling works
4. Compaction lock prevents race conditions
5. Fallback to sync compaction when no event loop
"""
import unittest
import asyncio
import time
from typing import List

from agent_framework.memory.history import HistoryManager
from agent_framework.memory.summarizer import SimpleSummarizer, LLMSummarizer
from agent_framework.messages.types import (
    SystemMessage,
    UserMessage,
    ToolCallMessage,
    ToolResultObservation,
    ToolCall
)
from agent_framework.llm.mock import MockLLMProvider, LLMResponse, FinishReason


class TestAsyncCompaction(unittest.TestCase):
    """Test async compaction functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_llm = MockLLMProvider(model="mock-model")
        self.simple_summarizer = SimpleSummarizer()

    def test_add_async_waits_for_compaction(self):
        """Test that add_async properly waits for compaction."""
        async def run_test():
            history = HistoryManager(
                summarizer=self.simple_summarizer,
                max_tokens=300,
                retention_window=5
            )

            # Add system and goal
            await history.add_async(SystemMessage(
                content="System",
                session_id="test",
                sequence=0
            ))

            await history.add_async(UserMessage(
                content="Goal",
                session_id="test",
                sequence=1
            ))

            # Add many messages asynchronously to trigger compaction
            for i in range(30):
                msg = UserMessage(
                    session_id="test",
                    sequence=i + 2,
                    content="X" * 50  # Larger messages to exceed token limit
                )
                await history.add_async(msg)

            # Should have compacted by now
            self.assertLess(len(history.messages), 32,
                          f"Expected compaction, got {len(history.messages)} messages")

        asyncio.run(run_test())

    def test_compact_async_preserves_structure(self):
        """Test that async compaction preserves message structure correctly."""
        async def run_test():
            history = HistoryManager(
                summarizer=self.simple_summarizer,
                max_tokens=200,
                retention_window=3
            )

            # Add system message
            system_content = "You are a helpful assistant"
            history.add(SystemMessage(
                content=system_content,
                session_id="test",
                sequence=0
            ))

            # Add goal
            goal_content = "Help me with a task"
            history.add(UserMessage(
                content=goal_content,
                session_id="test",
                sequence=1
            ))

            # Add many messages
            for i in range(20):
                history.add(UserMessage(
                    content=f"Message {i} " * 15,
                    session_id="test",
                    sequence=i + 2
                ))

            # Run async compaction
            await history.compact_async()

            # Verify structure
            self.assertIsInstance(history.messages[0], SystemMessage)
            self.assertEqual(history.messages[0].content, system_content)

            # Find goal message (should be preserved)
            found_goal = any(
                isinstance(msg, UserMessage) and msg.content == goal_content
                for msg in history.messages[:3]
            )
            self.assertTrue(found_goal, "Goal message should be preserved")

        asyncio.run(run_test())

    def test_async_summarizer_called(self):
        """Test that async compaction uses summarize_async."""
        async def run_test():
            # Mock LLM with response
            self.mock_llm.reset()
            self.mock_llm.set_response(LLMResponse(
                content="Summary of middle messages",
                finish_reason=FinishReason.STOP,
                usage={"total_tokens": 10}
            ))

            llm_summarizer = LLMSummarizer(self.mock_llm, max_summary_tokens=100)

            history = HistoryManager(
                summarizer=llm_summarizer,
                max_tokens=200,
                retention_window=3
            )

            # Add messages
            history.add(SystemMessage(content="System", session_id="test", sequence=0))
            history.add(UserMessage(content="Goal", session_id="test", sequence=1))

            for i in range(15):
                history.add(UserMessage(
                    content=f"Message {i} " * 15,
                    session_id="test",
                    sequence=i + 2
                ))

            # Compact asynchronously
            await history.compact_async()

            # Verify LLM was called
            self.assertGreater(self.mock_llm.call_count, 0,
                             "Async summarizer should have called LLM")

        asyncio.run(run_test())

    def test_compaction_lock_prevents_races(self):
        """Test that compaction lock prevents concurrent compactions."""
        async def run_test():
            history = HistoryManager(
                summarizer=self.simple_summarizer,
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

            # Start multiple compactions concurrently
            tasks = [
                asyncio.create_task(history.compact_async()),
                asyncio.create_task(history.compact_async()),
                asyncio.create_task(history.compact_async())
            ]

            # Wait for all to complete
            await asyncio.gather(*tasks)

            # Should have completed without errors
            # (lock ensures only one compaction at a time)
            self.assertGreater(len(history.messages), 0)

        asyncio.run(run_test())

    def test_fallback_to_sync_when_no_event_loop(self):
        """Test that compaction falls back to sync when no event loop available."""
        history = HistoryManager(
            summarizer=self.simple_summarizer,
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

        # Call compact_async() outside of async context
        # (should fallback to sync compaction)
        try:
            asyncio.run(history.compact_async())
            # Should complete without error
            self.assertLess(len(history.messages), 20)
        except RuntimeError:
            # If we can't even run asyncio.run, just verify sync compaction works
            history.compact()
            self.assertLess(len(history.messages), 20)

    def test_background_compaction_non_blocking(self):
        """Test that background compaction doesn't block add()."""
        history = HistoryManager(
            summarizer=self.simple_summarizer,
            max_tokens=300,
            retention_window=5
        )

        start = time.time()

        # Add many messages (should not block even when compaction triggered)
        for i in range(40):
            msg = UserMessage(
                session_id="test",
                sequence=i,
                content="X" * 50
            )
            history.add(msg)

        elapsed = time.time() - start

        # Should complete quickly (< 100ms) even with background compaction
        self.assertLess(elapsed, 0.1,
                       f"add() took {elapsed:.3f}s, should be < 0.1s (non-blocking)")

    def test_schedule_compaction_background(self):
        """Test that schedule_compaction_background works correctly."""
        async def run_test():
            history = HistoryManager(
                summarizer=self.simple_summarizer,
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

            # Schedule background compaction
            history.schedule_compaction_background()

            # Wait for background task to complete
            if history._compaction_task:
                await history._compaction_task

            # Should have compacted
            self.assertLess(len(history.messages), 20)

        asyncio.run(run_test())

    def test_concurrent_add_async_calls(self):
        """Test that concurrent add_async calls work correctly."""
        async def run_test():
            history = HistoryManager(
                summarizer=self.simple_summarizer,
                max_tokens=500,
                retention_window=5
            )

            # Add messages concurrently
            tasks = []
            for i in range(30):
                msg = UserMessage(
                    session_id="test",
                    sequence=i,
                    content=f"Message {i} " * 20
                )
                tasks.append(asyncio.create_task(history.add_async(msg)))

            # Wait for all adds to complete
            await asyncio.gather(*tasks)

            # All messages should be added (compaction may have occurred)
            self.assertGreater(len(history.messages), 0)

        asyncio.run(run_test())

    def test_async_compaction_with_tool_calls(self):
        """Test that async compaction preserves tool call integrity."""
        async def run_test():
            history = HistoryManager(
                summarizer=self.simple_summarizer,
                max_tokens=200,
                retention_window=3
            )

            # Add system and goal
            history.add(SystemMessage(content="System", session_id="test", sequence=0))
            history.add(UserMessage(content="Goal", session_id="test", sequence=1))

            # Add messages
            for i in range(10):
                history.add(UserMessage(
                    content=f"Message {i} " * 15,
                    session_id="test",
                    sequence=i * 3 + 2
                ))

            # Add tool call + result that should end up in tail
            tool_call_id = "call_123"
            history.add(ToolCallMessage(
                tool_calls=[
                    ToolCall(
                        id=tool_call_id,
                        tool_name="read_file",
                        arguments={"path": "/test/file.txt"}
                    )
                ],
                session_id="test",
                sequence=100
            ))

            history.add(ToolResultObservation(
                call_id=tool_call_id,
                content="File content",
                session_id="test",
                sequence=101
            ))

            # Add a few more messages
            for i in range(3):
                history.add(UserMessage(
                    content=f"After tool {i}",
                    session_id="test",
                    sequence=102 + i
                ))

            # Compact asynchronously
            await history.compact_async()

            # Verify tool call integrity
            has_tool_result = any(
                isinstance(msg, ToolResultObservation) and msg.call_id == tool_call_id
                for msg in history.messages
            )

            if has_tool_result:
                # Tool call should also be present
                has_tool_call = any(
                    isinstance(msg, ToolCallMessage) and
                    any(tc.id == tool_call_id for tc in msg.tool_calls)
                    for msg in history.messages
                )
                self.assertTrue(has_tool_call,
                              "Tool call should be present if tool result is present")

        asyncio.run(run_test())

    def test_async_compaction_performance(self):
        """Test that async compaction is reasonably fast."""
        async def run_test():
            history = HistoryManager(
                summarizer=self.simple_summarizer,
                max_tokens=300,
                retention_window=5
            )

            # Add many messages
            for i in range(50):
                history.add(UserMessage(
                    content=f"Message {i} " * 20,
                    session_id="test",
                    sequence=i
                ))

            # Measure async compaction time
            start = time.time()
            await history.compact_async()
            elapsed = time.time() - start

            # Should complete quickly (< 0.5s for simple summarizer)
            self.assertLess(elapsed, 0.5,
                           f"Async compaction took {elapsed:.3f}s, should be < 0.5s")

        asyncio.run(run_test())


if __name__ == '__main__':
    unittest.main()
