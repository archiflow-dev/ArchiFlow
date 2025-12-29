"""
Integration tests for HistoryManager compaction strategy.

Tests verify:
1. Compaction triggers when token limit is exceeded
2. Anchors are preserved (system message, first user message, last N messages)
3. Tool call integrity is maintained (no orphaned tool results)
4. Summary quality and accuracy
5. TODO auto-removal functionality
"""
import unittest
import asyncio
from typing import List

from agent_framework.memory.history import HistoryManager
from agent_framework.memory.summarizer import (
    SimpleSummarizer,
    LLMSummarizer,
    HybridSummarizer
)
from agent_framework.messages.types import (
    SystemMessage,
    UserMessage,
    ToolCallMessage,
    ToolResultObservation,
    LLMRespondMessage,
    ToolCall
)
from agent_framework.llm.mock import MockLLMProvider, LLMResponse, FinishReason
from agent_framework.llm.model_config import ModelConfig


class TestHistoryCompaction(unittest.TestCase):
    """Test history compaction behavior."""

    def setUp(self):
        """Set up test fixtures."""
        # Create mock LLM for summarization
        self.mock_llm = MockLLMProvider(model="mock-model")

        # Create summarizers
        self.simple_summarizer = SimpleSummarizer()
        self.llm_summarizer = LLMSummarizer(self.mock_llm, max_summary_tokens=100)

        # Create model config
        self.model_config = ModelConfig(
            model_name="gpt-4",
            context_window=8000,
            max_output_tokens=4000
        )

    def test_compaction_triggers_at_token_limit(self):
        """Test that compaction is triggered when token limit is exceeded."""
        # Create history with very low token limit
        history = HistoryManager(
            summarizer=self.simple_summarizer,
            max_tokens=100,  # Very low limit
            retention_window=5
        )

        # Add system message
        history.add(SystemMessage(
            content="You are a helpful assistant.",
            session_id="test",
            sequence=0
        ))

        # Add first user message (goal)
        history.add(UserMessage(
            content="Help me build a web application.",
            session_id="test",
            sequence=1
        ))

        # Track message count before adding many messages
        initial_count = len(history.messages)

        # Add many messages to exceed token limit
        for i in range(20):
            history.add(UserMessage(
                content=f"This is message {i} with some content to increase token count. " * 10,
                session_id="test",
                sequence=i + 2
            ))

        # Verify compaction occurred (message count should be less than 22)
        self.assertLess(
            len(history.messages),
            22,
            "Compaction should have reduced message count"
        )

        # Verify we have a summary message
        has_summary = any(
            isinstance(msg, SystemMessage) and "[Compacted" in msg.content
            for msg in history.messages
        )
        self.assertTrue(has_summary, "Should have a summary message after compaction")

    def test_anchor_preservation_system_message(self):
        """Test that system message at index 0 is always preserved."""
        history = HistoryManager(
            summarizer=self.simple_summarizer,
            max_tokens=200,
            retention_window=3
        )

        system_content = "You are a helpful assistant."
        history.add(SystemMessage(
            content=system_content,
            session_id="test",
            sequence=0
        ))

        # Add many messages to trigger compaction
        for i in range(15):
            history.add(UserMessage(
                content=f"Message {i} " * 20,
                session_id="test",
                sequence=i + 1
            ))

        # Force compaction
        history.compact()

        # Verify system message is still at index 0
        self.assertIsInstance(history.messages[0], SystemMessage)
        self.assertEqual(history.messages[0].content, system_content)

    def test_anchor_preservation_first_user_message(self):
        """Test that first user message (goal) is preserved."""
        history = HistoryManager(
            summarizer=self.simple_summarizer,
            max_tokens=200,
            retention_window=3
        )

        # Add system message
        history.add(SystemMessage(
            content="You are a helpful assistant.",
            session_id="test",
            sequence=0
        ))

        # Add first user message (goal)
        goal_content = "Build a web application for managing tasks."
        history.add(UserMessage(
            content=goal_content,
            session_id="test",
            sequence=1
        ))

        # Add many messages to trigger compaction
        for i in range(15):
            history.add(UserMessage(
                content=f"Message {i} " * 20,
                session_id="test",
                sequence=i + 2
            ))

        # Force compaction
        history.compact()

        # Verify first user message is preserved (should be at index 1, after system)
        found_goal = False
        for msg in history.messages[:3]:  # Check first few messages
            if isinstance(msg, UserMessage) and msg.content == goal_content:
                found_goal = True
                break

        self.assertTrue(found_goal, "First user message (goal) should be preserved")

    def test_anchor_preservation_last_n_messages(self):
        """Test that last N messages are preserved (retention window)."""
        retention_window = 5
        history = HistoryManager(
            summarizer=self.simple_summarizer,
            max_tokens=150,
            retention_window=retention_window
        )

        # Add system and goal
        history.add(SystemMessage(content="System", session_id="test", sequence=0))
        history.add(UserMessage(content="Goal", session_id="test", sequence=1))

        # Add numbered messages
        message_ids = []
        for i in range(20):
            msg_id = f"message_{i}"
            message_ids.append(msg_id)
            history.add(UserMessage(
                content=f"{msg_id} " * 15,
                session_id="test",
                sequence=i + 2
            ))

        # Force compaction
        history.compact()

        # Verify last N messages are present
        # The last retention_window messages should be in the history
        last_n_ids = message_ids[-retention_window:]

        for msg_id in last_n_ids:
            found = any(msg_id in msg.content for msg in history.messages if hasattr(msg, 'content'))
            self.assertTrue(found, f"Last N messages should include {msg_id}")

    def test_tool_call_integrity_no_orphaned_results(self):
        """Test that tool results in tail always have their corresponding tool calls."""
        history = HistoryManager(
            summarizer=self.simple_summarizer,
            max_tokens=200,
            retention_window=3
        )

        # Add system and goal
        history.add(SystemMessage(content="System", session_id="test", sequence=0))
        history.add(UserMessage(content="Goal", session_id="test", sequence=1))

        # Add many messages in the middle
        for i in range(10):
            history.add(UserMessage(
                content=f"Middle message {i} " * 15,
                session_id="test",
                sequence=i + 2
            ))

        # Add tool call + result that should end up in the tail
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
            content="File content here",
            session_id="test",
            sequence=101
        ))

        # Add a few more messages to ensure result is in tail
        for i in range(3):
            history.add(UserMessage(
                content=f"After tool result {i}",
                session_id="test",
                sequence=102 + i
            ))

        # Force compaction
        history.compact()

        # Verify that if tool result is present, its tool call is also present
        has_tool_result = any(
            isinstance(msg, ToolResultObservation) and msg.call_id == tool_call_id
            for msg in history.messages
        )

        if has_tool_result:
            # Find the tool call
            has_tool_call = any(
                isinstance(msg, ToolCallMessage) and
                any(tc.id == tool_call_id for tc in msg.tool_calls)
                for msg in history.messages
            )
            self.assertTrue(
                has_tool_call,
                "Tool call should be present if tool result is in history"
            )

    def test_summary_generation_simple(self):
        """Test simple summarizer generates accurate summaries."""
        history = HistoryManager(
            summarizer=self.simple_summarizer,
            max_tokens=150,
            retention_window=3
        )

        # Add messages
        history.add(SystemMessage(content="System", session_id="test", sequence=0))
        history.add(UserMessage(content="Goal", session_id="test", sequence=1))

        # Add messages with tool calls
        for i in range(10):
            history.add(UserMessage(
                content=f"Message {i} " * 15,
                session_id="test",
                sequence=i + 2
            ))

        history.add(ToolCallMessage(
            tool_calls=[
                ToolCall(id="call_1", tool_name="read_file", arguments={}),
                ToolCall(id="call_2", tool_name="write_file", arguments={})
            ],
            session_id="test",
            sequence=100
        ))

        # Force compaction
        history.compact()

        # Find summary message
        summary_msg = None
        for msg in history.messages:
            if isinstance(msg, SystemMessage) and "[Compacted" in msg.content:
                summary_msg = msg
                break

        self.assertIsNotNone(summary_msg, "Should have a summary message")
        self.assertIn("Compacted", summary_msg.content)

    def test_summary_generation_llm(self):
        """Test LLM summarizer generates summaries using LLM."""
        # Mock LLM response for summarization
        self.mock_llm.set_response(LLMResponse(
            content="User requested task management features, agent performed file operations.",
            finish_reason=FinishReason.STOP,
            usage={"total_tokens": 15}
        ))

        history = HistoryManager(
            summarizer=self.llm_summarizer,
            max_tokens=150,
            retention_window=3
        )

        # Add messages
        history.add(SystemMessage(content="System", session_id="test", sequence=0))
        history.add(UserMessage(content="Build task manager", session_id="test", sequence=1))

        for i in range(10):
            history.add(UserMessage(
                content=f"Message {i} " * 15,
                session_id="test",
                sequence=i + 2
            ))

        # Force compaction
        history.compact()

        # Verify LLM was called
        self.assertGreater(self.mock_llm.call_count, 0, "LLM should have been called for summarization")

        # Find summary message
        summary_msg = None
        for msg in history.messages:
            if isinstance(msg, SystemMessage) and "[Summary" in msg.content:
                summary_msg = msg
                break

        self.assertIsNotNone(summary_msg, "Should have a summary message")

    def test_todo_auto_removal(self):
        """Test that old TODO messages are automatically removed when new ones are added."""
        history = HistoryManager(
            summarizer=self.simple_summarizer,
            max_tokens=5000,  # High limit so compaction doesn't interfere
            retention_window=5,
            auto_remove_old_todos=True
        )

        # Add system message
        history.add(SystemMessage(content="System", session_id="test", sequence=0))

        # Add first TODO
        history.add(ToolCallMessage(
            tool_calls=[
                ToolCall(id="todo_1", tool_name="todo_write", arguments={"todos": ["Task 1"]})
            ],
            session_id="test",
            sequence=1
        ))

        history.add(ToolResultObservation(
            call_id="todo_1",
            content="TODO updated",
            session_id="test",
            sequence=2
        ))

        # Add many messages to push TODO outside retention window
        for i in range(10):
            history.add(UserMessage(
                content=f"Message {i}",
                session_id="test",
                sequence=i + 3
            ))

        # Verify first TODO is still in history (for now)
        has_first_todo = any(
            isinstance(msg, ToolResultObservation) and msg.call_id == "todo_1"
            for msg in history.messages
        )

        # Add second TODO (should trigger removal of first TODO if outside retention window)
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

        # Verify first TODO was removed (it's outside retention window)
        has_first_todo_after = any(
            isinstance(msg, ToolResultObservation) and msg.call_id == "todo_1"
            for msg in history.messages
        )

        self.assertFalse(
            has_first_todo_after,
            "Old TODO outside retention window should be removed when new TODO is added"
        )

        # Verify second TODO is still present
        has_second_todo = any(
            isinstance(msg, ToolResultObservation) and msg.call_id == "todo_2"
            for msg in history.messages
        )
        self.assertTrue(has_second_todo, "New TODO should be present")

    def test_todo_auto_removal_respects_retention_window(self):
        """Test that TODO auto-removal respects retention window."""
        history = HistoryManager(
            summarizer=self.simple_summarizer,
            max_tokens=5000,
            retention_window=10,  # Large window
            auto_remove_old_todos=True
        )

        # Add system message
        history.add(SystemMessage(content="System", session_id="test", sequence=0))

        # Add first TODO
        history.add(ToolCallMessage(
            tool_calls=[
                ToolCall(id="todo_1", tool_name="todo_write", arguments={"todos": ["Task 1"]})
            ],
            session_id="test",
            sequence=1
        ))

        history.add(ToolResultObservation(
            call_id="todo_1",
            content="TODO updated",
            session_id="test",
            sequence=2
        ))

        # Add only a few messages (TODO stays within retention window)
        for i in range(3):
            history.add(UserMessage(
                content=f"Message {i}",
                session_id="test",
                sequence=i + 3
            ))

        # Add second TODO
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

        # Verify first TODO is STILL present (within retention window)
        has_first_todo = any(
            isinstance(msg, ToolResultObservation) and msg.call_id == "todo_1"
            for msg in history.messages
        )

        self.assertTrue(
            has_first_todo,
            "TODO within retention window should NOT be removed"
        )

    def test_hybrid_summarizer_uses_llm_for_large_chunks(self):
        """Test that hybrid summarizer uses LLM for large message chunks."""
        # Reset mock LLM state
        self.mock_llm.reset()

        # Mock LLM response
        self.mock_llm.set_response(LLMResponse(
            content="Detailed summary of large conversation chunk.",
            finish_reason=FinishReason.STOP,
            usage={"total_tokens": 20}
        ))

        hybrid_summarizer = HybridSummarizer(
            llm=self.mock_llm,
            threshold=5,  # Use LLM for > 5 messages
            max_summary_tokens=100
        )

        # Create a large chunk of messages (> threshold)
        messages = []
        for i in range(10):  # 10 messages > 5 threshold
            messages.append(UserMessage(
                content=f"Message {i}",
                session_id="test",
                sequence=i
            ))

        # Call summarize directly
        summary = hybrid_summarizer.summarize(messages)

        # Verify LLM was called
        self.assertGreater(
            self.mock_llm.call_count,
            0,
            "Hybrid summarizer should use LLM for chunks > threshold"
        )

        # Verify summary contains expected content
        self.assertIn("Summary", summary)

    def test_hybrid_summarizer_uses_simple_for_small_chunks(self):
        """Test that hybrid summarizer uses simple summarization for small chunks."""
        # Reset mock LLM state
        self.mock_llm.reset()

        hybrid_summarizer = HybridSummarizer(
            llm=self.mock_llm,
            threshold=10,  # Use LLM for > 10 messages
            max_summary_tokens=100
        )

        # Create a small chunk of messages (< threshold)
        messages = []
        for i in range(3):  # 3 messages < 10 threshold
            messages.append(UserMessage(
                content=f"Message {i}",
                session_id="test",
                sequence=i
            ))

        # Call summarize directly
        summary = hybrid_summarizer.summarize(messages)

        # Verify LLM was NOT called (should use simple summarizer)
        self.assertEqual(
            self.mock_llm.call_count,
            0,
            "Hybrid summarizer should use simple summarizer for chunks < threshold"
        )

        # Verify summary contains expected format from simple summarizer
        self.assertIn("Compacted", summary)

    def test_no_compaction_when_under_limit(self):
        """Test that compaction is NOT triggered when under token limit."""
        history = HistoryManager(
            summarizer=self.simple_summarizer,
            max_tokens=10000,  # Very high limit
            retention_window=5
        )

        # Add messages
        history.add(SystemMessage(content="System", session_id="test", sequence=0))
        history.add(UserMessage(content="Goal", session_id="test", sequence=1))

        for i in range(5):
            history.add(UserMessage(
                content=f"Message {i}",
                session_id="test",
                sequence=i + 2
            ))

        initial_count = len(history.messages)

        # Force compaction call (but it should be a no-op)
        history.compact()

        # Verify message count didn't change (no compaction occurred)
        self.assertEqual(
            len(history.messages),
            initial_count,
            "No compaction should occur when message count is small"
        )

    def test_token_estimate_accuracy(self):
        """Test that token estimation is reasonably accurate."""
        history = HistoryManager(
            summarizer=self.simple_summarizer,
            max_tokens=5000,
            retention_window=5
        )

        # Add a message with known length
        content = "X" * 400  # 400 characters
        history.add(UserMessage(
            content=content,
            session_id="test",
            sequence=0
        ))

        # Get token estimate
        tokens = history.get_token_estimate()

        # Should be approximately 400 / 4 = 100 tokens
        # Allow for some variance (±20%)
        expected_tokens = 100
        self.assertGreater(tokens, expected_tokens * 0.8)
        self.assertLess(tokens, expected_tokens * 1.2)


if __name__ == '__main__':
    unittest.main()
