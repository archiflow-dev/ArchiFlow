"""
Performance tests for HistoryManager compaction.

Tests verify:
1. Compaction completes within acceptable time limits
2. Memory usage stays within bounds
3. Token counting performance is adequate
4. Summarization performance is acceptable
"""
import unittest
import time
import sys
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


class TestHistoryPerformance(unittest.TestCase):
    """Test history compaction performance."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_llm = MockLLMProvider(model="mock-model")
        self.simple_summarizer = SimpleSummarizer()

    def test_compaction_performance_large_history(self):
        """Test that compaction completes quickly even with large history."""
        history = HistoryManager(
            summarizer=self.simple_summarizer,
            max_tokens=500,
            retention_window=10
        )

        # Add system and goal
        history.add(SystemMessage(content="System", session_id="test", sequence=0))
        history.add(UserMessage(content="Goal", session_id="test", sequence=1))

        # Add many messages
        num_messages = 100
        for i in range(num_messages):
            history.add(UserMessage(
                content=f"Message {i} " * 20,
                session_id="test",
                sequence=i + 2
            ))

        # Measure compaction time
        start_time = time.time()
        history.compact()
        end_time = time.time()

        compaction_time = end_time - start_time

        # Compaction should complete in < 1 second for 100 messages
        self.assertLess(
            compaction_time,
            1.0,
            f"Compaction took {compaction_time:.3f}s, should be < 1.0s"
        )

        print(f"\nCompaction of {num_messages} messages took {compaction_time:.3f}s")

    def test_token_counting_performance(self):
        """Test that token counting is fast for large histories."""
        history = HistoryManager(
            summarizer=self.simple_summarizer,
            max_tokens=10000,
            retention_window=10
        )

        # Add many messages
        num_messages = 200
        for i in range(num_messages):
            history.add(UserMessage(
                content=f"Message {i} with some content to count " * 15,
                session_id="test",
                sequence=i
            ))

        # Measure token counting time
        start_time = time.time()
        for _ in range(100):  # Count 100 times to get meaningful measurement
            _ = history.get_token_estimate()
        end_time = time.time()

        count_time = end_time - start_time
        avg_time = count_time / 100

        # Token counting should be very fast (< 10ms average)
        self.assertLess(
            avg_time,
            0.01,
            f"Token counting took {avg_time*1000:.1f}ms on average, should be < 10ms"
        )

        print(f"\nToken counting for {num_messages} messages took {avg_time*1000:.3f}ms on average")

    def test_add_message_performance(self):
        """Test that adding messages is fast, even with compaction checks."""
        history = HistoryManager(
            summarizer=self.simple_summarizer,
            max_tokens=5000,
            retention_window=10
        )

        num_messages = 500
        start_time = time.time()

        for i in range(num_messages):
            history.add(UserMessage(
                content=f"Message {i}",
                session_id="test",
                sequence=i
            ))

        end_time = time.time()
        total_time = end_time - start_time
        avg_time = total_time / num_messages

        # Adding messages should be fast (< 1ms per message on average)
        self.assertLess(
            avg_time,
            0.001,
            f"Adding messages took {avg_time*1000:.3f}ms on average, should be < 1ms"
        )

        print(f"\nAdding {num_messages} messages took {total_time:.3f}s ({avg_time*1000:.3f}ms per message)")

    def test_memory_usage_with_compaction(self):
        """Test that compaction effectively reduces memory usage."""
        history = HistoryManager(
            summarizer=self.simple_summarizer,
            max_tokens=300,
            retention_window=5
        )

        # Add system and goal
        history.add(SystemMessage(content="System", session_id="test", sequence=0))
        history.add(UserMessage(content="Goal", session_id="test", sequence=1))

        # Add many large messages
        for i in range(50):
            history.add(UserMessage(
                content=f"Large message {i} " * 50,
                session_id="test",
                sequence=i + 2
            ))

        # Get final message count (should be compacted)
        final_count = len(history.messages)

        # Verify compaction occurred (should have far fewer than 52 messages)
        self.assertLess(
            final_count,
            30,
            f"Compaction should have reduced message count to < 30, got {final_count}"
        )

        print(f"\n50 messages compacted to {final_count} messages")

    def test_tool_call_extension_performance(self):
        """Test that extending tail for tool calls doesn't significantly slow compaction."""
        history = HistoryManager(
            summarizer=self.simple_summarizer,
            max_tokens=300,
            retention_window=5
        )

        # Add system and goal
        history.add(SystemMessage(content="System", session_id="test", sequence=0))
        history.add(UserMessage(content="Goal", session_id="test", sequence=1))

        # Add messages with many tool calls
        for i in range(30):
            # Add user message
            history.add(UserMessage(
                content=f"Message {i} " * 20,
                session_id="test",
                sequence=i * 3 + 2
            ))

            # Add tool call
            tool_call_id = f"call_{i}"
            history.add(ToolCallMessage(
                tool_calls=[
                    ToolCall(
                        id=tool_call_id,
                        tool_name=f"tool_{i % 5}",
                        arguments={"param": f"value_{i}"}
                    )
                ],
                session_id="test",
                sequence=i * 3 + 3
            ))

            # Add tool result
            history.add(ToolResultObservation(
                call_id=tool_call_id,
                content=f"Result for call {i}",
                session_id="test",
                sequence=i * 3 + 4
            ))

        # Measure compaction time with tool call extension
        start_time = time.time()
        history.compact()
        end_time = time.time()

        compaction_time = end_time - start_time

        # Compaction with tool call extension should still be fast (< 0.5s)
        self.assertLess(
            compaction_time,
            0.5,
            f"Compaction with tool calls took {compaction_time:.3f}s, should be < 0.5s"
        )

        print(f"\nCompaction with 30 tool call pairs took {compaction_time:.3f}s")

    def test_todo_auto_removal_performance(self):
        """Test that TODO auto-removal is fast and doesn't slow down message addition."""
        history = HistoryManager(
            summarizer=self.simple_summarizer,
            max_tokens=5000,
            retention_window=10,
            auto_remove_old_todos=True
        )

        num_todo_updates = 50
        start_time = time.time()

        for i in range(num_todo_updates):
            # Add some messages between TODO updates
            for j in range(5):
                history.add(UserMessage(
                    content=f"Message {i}_{j}",
                    session_id="test",
                    sequence=i * 10 + j
                ))

            # Add TODO update
            history.add(ToolCallMessage(
                tool_calls=[
                    ToolCall(
                        id=f"todo_{i}",
                        tool_name="todo_write",
                        arguments={"todos": [f"Task {i}"]}
                    )
                ],
                session_id="test",
                sequence=i * 10 + 5
            ))

            history.add(ToolResultObservation(
                call_id=f"todo_{i}",
                content="TODO updated",
                session_id="test",
                sequence=i * 10 + 6
            ))

        end_time = time.time()
        total_time = end_time - start_time

        # All operations should complete quickly (< 2s for 50 TODO updates)
        self.assertLess(
            total_time,
            2.0,
            f"TODO auto-removal operations took {total_time:.3f}s, should be < 2.0s"
        )

        print(f"\n{num_todo_updates} TODO updates with auto-removal took {total_time:.3f}s")

    def test_llm_summarizer_fallback_performance(self):
        """Test that LLM summarizer fallback to simple summarizer is fast."""
        # Mock LLM that always fails
        failing_llm = MockLLMProvider(model="mock-model")

        class FailingLLM(MockLLMProvider):
            def generate(self, messages, tools=None, **kwargs):
                raise Exception("Simulated LLM failure")

        failing_llm = FailingLLM()
        llm_summarizer = LLMSummarizer(failing_llm, max_summary_tokens=100)

        history = HistoryManager(
            summarizer=llm_summarizer,
            max_tokens=200,
            retention_window=3
        )

        # Add messages
        history.add(SystemMessage(content="System", session_id="test", sequence=0))
        history.add(UserMessage(content="Goal", session_id="test", sequence=1))

        for i in range(20):
            history.add(UserMessage(
                content=f"Message {i} " * 15,
                session_id="test",
                sequence=i + 2
            ))

        # Measure fallback compaction time
        start_time = time.time()
        history.compact()
        end_time = time.time()

        compaction_time = end_time - start_time

        # Fallback should still be fast (< 0.5s)
        self.assertLess(
            compaction_time,
            0.5,
            f"Fallback compaction took {compaction_time:.3f}s, should be < 0.5s"
        )

        print(f"\nFallback compaction (LLM failed) took {compaction_time:.3f}s")

    def test_scaling_with_retention_window(self):
        """Test that compaction time doesn't scale poorly with retention window size."""
        results = []

        for window_size in [5, 10, 20, 50]:
            history = HistoryManager(
                summarizer=self.simple_summarizer,
                max_tokens=300,
                retention_window=window_size
            )

            # Add many messages
            history.add(SystemMessage(content="System", session_id="test", sequence=0))
            history.add(UserMessage(content="Goal", session_id="test", sequence=1))

            for i in range(100):
                history.add(UserMessage(
                    content=f"Message {i} " * 20,
                    session_id="test",
                    sequence=i + 2
                ))

            # Measure compaction time
            start_time = time.time()
            history.compact()
            end_time = time.time()

            compaction_time = end_time - start_time
            results.append((window_size, compaction_time))

        # Print results
        print("\nCompaction time vs retention window size:")
        for window_size, compaction_time in results:
            print(f"  Window {window_size:3d}: {compaction_time:.4f}s")

        # Verify all compactions completed quickly (< 0.5s each)
        for window_size, compaction_time in results:
            self.assertLess(
                compaction_time,
                0.5,
                f"Compaction with window={window_size} took {compaction_time:.3f}s, should be < 0.5s"
            )


if __name__ == '__main__':
    unittest.main(verbosity=2)
