"""
Tests for CompactionStrategy (Task 3.1.2).

Tests verify:
1. SelectiveRetentionStrategy behavior (anchor method)
2. SlidingWindowStrategy behavior (simple window)
3. Tool call/result preservation
4. Edge cases and boundary conditions
"""
import unittest

from agent_framework.memory.compaction_strategy import (
    CompactionAnalysis,
    SelectiveRetentionStrategy,
    SlidingWindowStrategy,
)
from agent_framework.messages.types import (
    BatchToolResultObservation,
    LLMRespondMessage,
    SystemMessage,
    ToolCall,
    ToolCallMessage,
    ToolResultObservation,
    UserMessage,
)


class TestSelectiveRetentionStrategy(unittest.TestCase):
    """Test SelectiveRetentionStrategy (anchor method)."""

    def setUp(self):
        """Set up test fixtures."""
        self.strategy = SelectiveRetentionStrategy()

    def test_not_enough_messages_to_compact(self):
        """Test that strategy returns all messages when count <= retention_window + 2."""
        messages = [
            SystemMessage(content="System", session_id="test", sequence=0),
            UserMessage(content="Goal", session_id="test", sequence=1),
            LLMRespondMessage(content="Response", session_id="test", sequence=2),
        ]

        analysis = self.strategy.analyze(messages, retention_window=10)

        # All messages should be in preserved_head (nothing to compact)
        self.assertEqual(len(analysis.preserved_head), 3)
        self.assertEqual(len(analysis.middle_chunk), 0)
        self.assertEqual(len(analysis.preserved_tail), 0)

    def test_basic_compaction(self):
        """Test basic selective retention with head, middle, and tail."""
        messages = [
            SystemMessage(content="System", session_id="test", sequence=0),
            UserMessage(content="Goal", session_id="test", sequence=1),
            LLMRespondMessage(content="Middle 1", session_id="test", sequence=2),
            LLMRespondMessage(content="Middle 2", session_id="test", sequence=3),
            LLMRespondMessage(content="Middle 3", session_id="test", sequence=4),
            LLMRespondMessage(content="Tail 1", session_id="test", sequence=5),
            LLMRespondMessage(content="Tail 2", session_id="test", sequence=6),
        ]

        analysis = self.strategy.analyze(messages, retention_window=2)

        # Head: SystemMessage + UserMessage (Goal)
        self.assertEqual(len(analysis.preserved_head), 2)
        self.assertIsInstance(analysis.preserved_head[0], SystemMessage)
        self.assertIsInstance(analysis.preserved_head[1], UserMessage)

        # Middle: Everything between head and tail
        self.assertEqual(len(analysis.middle_chunk), 3)
        self.assertEqual(analysis.middle_chunk[0].content, "Middle 1")
        self.assertEqual(analysis.middle_chunk[1].content, "Middle 2")
        self.assertEqual(analysis.middle_chunk[2].content, "Middle 3")

        # Tail: Last 2 messages
        self.assertEqual(len(analysis.preserved_tail), 2)
        self.assertEqual(analysis.preserved_tail[0].content, "Tail 1")
        self.assertEqual(analysis.preserved_tail[1].content, "Tail 2")

    def test_preserves_system_message(self):
        """Test that SystemMessage at index 0 is always preserved."""
        messages = [
            SystemMessage(content="System", session_id="test", sequence=0),
            UserMessage(content="User 1", session_id="test", sequence=1),
            LLMRespondMessage(content="Middle", session_id="test", sequence=2),
            UserMessage(content="Tail", session_id="test", sequence=3),
        ]

        analysis = self.strategy.analyze(messages, retention_window=1)

        # System message should be in head
        self.assertIn(messages[0], analysis.preserved_head)
        self.assertIsInstance(analysis.preserved_head[0], SystemMessage)

    def test_preserves_first_user_message(self):
        """Test that first UserMessage (goal) is preserved in head."""
        messages = [
            SystemMessage(content="System", session_id="test", sequence=0),
            UserMessage(content="Goal", session_id="test", sequence=1),
            LLMRespondMessage(content="Middle", session_id="test", sequence=2),
            UserMessage(content="Tail", session_id="test", sequence=3),
        ]

        analysis = self.strategy.analyze(messages, retention_window=1)

        # First user message should be in head
        self.assertEqual(len(analysis.preserved_head), 2)
        self.assertIsInstance(analysis.preserved_head[0], SystemMessage)
        self.assertIsInstance(analysis.preserved_head[1], UserMessage)
        self.assertEqual(analysis.preserved_head[1].content, "Goal")

    def test_no_system_message(self):
        """Test compaction when there's no SystemMessage at start."""
        messages = [
            UserMessage(content="Goal", session_id="test", sequence=0),
            LLMRespondMessage(content="Middle 1", session_id="test", sequence=1),
            LLMRespondMessage(content="Middle 2", session_id="test", sequence=2),
            UserMessage(content="Tail", session_id="test", sequence=3),
        ]

        analysis = self.strategy.analyze(messages, retention_window=1)

        # Head should contain first user message
        self.assertEqual(len(analysis.preserved_head), 1)
        self.assertIsInstance(analysis.preserved_head[0], UserMessage)
        self.assertEqual(analysis.preserved_head[0].content, "Goal")

    def test_tool_call_result_preservation(self):
        """Test that tool calls are preserved when their results are in tail."""
        messages = [
            SystemMessage(content="System", session_id="test", sequence=0),
            UserMessage(content="Goal", session_id="test", sequence=1),
            LLMRespondMessage(content="Middle", session_id="test", sequence=2),
            ToolCallMessage(
                tool_calls=[ToolCall(id="call_1", tool_name="test_tool", arguments={})],
                session_id="test",
                sequence=3
            ),
            ToolResultObservation(
                call_id="call_1",
                content="Result",
                session_id="test",
                sequence=4
            ),
        ]

        analysis = self.strategy.analyze(messages, retention_window=1)

        # Tail should be extended to include the tool call
        # Because tool result is in tail, tool call should also be included
        self.assertEqual(len(analysis.preserved_tail), 2)
        self.assertIsInstance(analysis.preserved_tail[0], ToolCallMessage)
        self.assertIsInstance(analysis.preserved_tail[1], ToolResultObservation)

    def test_batch_tool_results_preservation(self):
        """Test that tool calls are preserved for batch tool results."""
        class MockToolResult:
            def __init__(self, call_id, content):
                self.call_id = call_id
                self.content = content

        messages = [
            SystemMessage(content="System", session_id="test", sequence=0),
            UserMessage(content="Goal", session_id="test", sequence=1),
            ToolCallMessage(
                tool_calls=[
                    ToolCall(id="call_1", tool_name="tool1", arguments={}),
                    ToolCall(id="call_2", tool_name="tool2", arguments={}),
                ],
                session_id="test",
                sequence=2
            ),
            BatchToolResultObservation(
                results=[
                    MockToolResult("call_1", "Result 1"),
                    MockToolResult("call_2", "Result 2"),
                ],
                session_id="test",
                sequence=3
            ),
        ]

        analysis = self.strategy.analyze(messages, retention_window=1)

        # Tail should be extended to include the tool call message
        self.assertEqual(len(analysis.preserved_tail), 2)
        self.assertIsInstance(analysis.preserved_tail[0], ToolCallMessage)
        self.assertIsInstance(analysis.preserved_tail[1], BatchToolResultObservation)

    def test_multiple_tool_calls_in_middle(self):
        """Test that only relevant tool calls are preserved (those with results in tail)."""
        messages = [
            SystemMessage(content="System", session_id="test", sequence=0),
            UserMessage(content="Goal", session_id="test", sequence=1),
            ToolCallMessage(
                tool_calls=[ToolCall(id="old_call", tool_name="old", arguments={})],
                session_id="test",
                sequence=2
            ),
            ToolResultObservation(call_id="old_call", content="Old result", session_id="test", sequence=3),
            LLMRespondMessage(content="Middle", session_id="test", sequence=4),
            ToolCallMessage(
                tool_calls=[ToolCall(id="new_call", tool_name="new", arguments={})],
                session_id="test",
                sequence=5
            ),
            ToolResultObservation(call_id="new_call", content="New result", session_id="test", sequence=6),
        ]

        analysis = self.strategy.analyze(messages, retention_window=2)

        # Tail should include last 2 messages + the tool call for new_call
        # (Last 2 messages are the tool call and result at index 5-6)
        self.assertEqual(len(analysis.preserved_tail), 2)

        # Old tool call/result should be in middle
        self.assertGreater(len(analysis.middle_chunk), 0)

    def test_empty_messages_list(self):
        """Test compaction with empty messages list."""
        analysis = self.strategy.analyze([], retention_window=10)

        self.assertEqual(len(analysis.preserved_head), 0)
        self.assertEqual(len(analysis.middle_chunk), 0)
        self.assertEqual(len(analysis.preserved_tail), 0)


class TestSlidingWindowStrategy(unittest.TestCase):
    """Test SlidingWindowStrategy (simple window)."""

    def setUp(self):
        """Set up test fixtures."""
        self.strategy = SlidingWindowStrategy()

    def test_not_enough_messages_to_compact(self):
        """Test that strategy returns all messages when count <= retention_window."""
        messages = [
            UserMessage(content="Message 1", session_id="test", sequence=0),
            LLMRespondMessage(content="Message 2", session_id="test", sequence=1),
            UserMessage(content="Message 3", session_id="test", sequence=2),
        ]

        analysis = self.strategy.analyze(messages, retention_window=5)

        # All messages should be in tail (nothing to compact)
        self.assertEqual(len(analysis.preserved_head), 0)
        self.assertEqual(len(analysis.middle_chunk), 0)
        self.assertEqual(len(analysis.preserved_tail), 3)

    def test_basic_sliding_window(self):
        """Test basic sliding window with no head preservation."""
        messages = [
            SystemMessage(content="System", session_id="test", sequence=0),
            UserMessage(content="Old 1", session_id="test", sequence=1),
            LLMRespondMessage(content="Old 2", session_id="test", sequence=2),
            UserMessage(content="Recent 1", session_id="test", sequence=3),
            LLMRespondMessage(content="Recent 2", session_id="test", sequence=4),
        ]

        analysis = self.strategy.analyze(messages, retention_window=2)

        # No head (sliding window doesn't preserve anchors)
        self.assertEqual(len(analysis.preserved_head), 0)

        # Middle: Everything before the window (first 3 messages)
        self.assertEqual(len(analysis.middle_chunk), 3)
        self.assertEqual(analysis.middle_chunk[0].content, "System")
        self.assertEqual(analysis.middle_chunk[1].content, "Old 1")
        self.assertEqual(analysis.middle_chunk[2].content, "Old 2")

        # Tail: Last 2 messages
        self.assertEqual(len(analysis.preserved_tail), 2)
        self.assertEqual(analysis.preserved_tail[0].content, "Recent 1")
        self.assertEqual(analysis.preserved_tail[1].content, "Recent 2")

    def test_no_system_message_preservation(self):
        """Test that sliding window doesn't preserve SystemMessage specially."""
        messages = [
            SystemMessage(content="System", session_id="test", sequence=0),
            UserMessage(content="User 1", session_id="test", sequence=1),
            UserMessage(content="User 2", session_id="test", sequence=2),
        ]

        analysis = self.strategy.analyze(messages, retention_window=1)

        # System message should be in middle (to be summarized)
        self.assertEqual(len(analysis.preserved_head), 0)
        self.assertEqual(len(analysis.middle_chunk), 2)
        self.assertEqual(analysis.middle_chunk[0].content, "System")
        self.assertEqual(len(analysis.preserved_tail), 1)

    def test_tool_call_result_preservation(self):
        """Test that tool calls are preserved when their results are in window."""
        messages = [
            UserMessage(content="Old message", session_id="test", sequence=0),
            ToolCallMessage(
                tool_calls=[ToolCall(id="call_1", tool_name="test_tool", arguments={})],
                session_id="test",
                sequence=1
            ),
            ToolResultObservation(
                call_id="call_1",
                content="Result",
                session_id="test",
                sequence=2
            ),
        ]

        analysis = self.strategy.analyze(messages, retention_window=1)

        # Window should be extended to include tool call
        self.assertEqual(len(analysis.preserved_tail), 2)
        self.assertIsInstance(analysis.preserved_tail[0], ToolCallMessage)
        self.assertIsInstance(analysis.preserved_tail[1], ToolResultObservation)

    def test_batch_tool_results_preservation(self):
        """Test that tool calls are preserved for batch results in window."""
        class MockToolResult:
            def __init__(self, call_id, content):
                self.call_id = call_id
                self.content = content

        messages = [
            UserMessage(content="Old", session_id="test", sequence=0),
            ToolCallMessage(
                tool_calls=[
                    ToolCall(id="call_1", tool_name="tool1", arguments={}),
                    ToolCall(id="call_2", tool_name="tool2", arguments={}),
                ],
                session_id="test",
                sequence=1
            ),
            BatchToolResultObservation(
                results=[
                    MockToolResult("call_1", "Result 1"),
                    MockToolResult("call_2", "Result 2"),
                ],
                session_id="test",
                sequence=2
            ),
        ]

        analysis = self.strategy.analyze(messages, retention_window=1)

        # Window should be extended to include tool call message
        self.assertEqual(len(analysis.preserved_tail), 2)
        self.assertIsInstance(analysis.preserved_tail[0], ToolCallMessage)
        self.assertIsInstance(analysis.preserved_tail[1], BatchToolResultObservation)

    def test_empty_messages_list(self):
        """Test sliding window with empty messages list."""
        analysis = self.strategy.analyze([], retention_window=10)

        self.assertEqual(len(analysis.preserved_head), 0)
        self.assertEqual(len(analysis.middle_chunk), 0)
        self.assertEqual(len(analysis.preserved_tail), 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
