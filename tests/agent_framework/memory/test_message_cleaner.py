"""
Tests for MessageCleaner (Task 3.1.3).

Tests verify:
1. TODOCleaner removes old TODO messages
2. DuplicateCleaner removes duplicate messages
3. CompositeCleaner applies multiple cleaners
4. Retention window is respected
5. Integration with HistoryManager
"""
import unittest

from agent_framework.memory.message_cleaner import (
    CompositeCleaner,
    DuplicateCleaner,
    TODOCleaner,
)
from agent_framework.messages.types import (
    LLMRespondMessage,
    ToolCall,
    ToolCallMessage,
    ToolResultObservation,
    UserMessage,
)


class TestTODOCleaner(unittest.TestCase):
    """Test TODOCleaner functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.cleaner = TODOCleaner()

    def test_empty_messages(self):
        """Test that cleaner handles empty message list."""
        result = self.cleaner.clean([], retention_window=10)
        self.assertEqual(result, [])

    def test_no_todos(self):
        """Test that cleaner leaves non-TODO messages unchanged."""
        messages = [
            UserMessage(content="Hello", session_id="test", sequence=0),
            LLMRespondMessage(content="Hi", session_id="test", sequence=1),
        ]

        result = self.cleaner.clean(messages, retention_window=10)
        self.assertEqual(len(result), 2)
        self.assertEqual(result, messages)

    def test_removes_old_todos(self):
        """Test that cleaner removes TODO messages outside retention window."""
        messages = [
            UserMessage(content="Message 1", session_id="test", sequence=0),
            ToolCallMessage(
                tool_calls=[ToolCall(id="todo_1", tool_name="todo_write", arguments={})],
                session_id="test",
                sequence=1
            ),
            ToolResultObservation(
                call_id="todo_1",
                content="TODO updated",
                session_id="test",
                sequence=2
            ),
            LLMRespondMessage(content="Middle", session_id="test", sequence=3),
            LLMRespondMessage(content="Recent 1", session_id="test", sequence=4),
            LLMRespondMessage(content="Recent 2", session_id="test", sequence=5),
        ]

        # Retention window of 2 means last 2 messages are protected
        result = self.cleaner.clean(messages, retention_window=2)

        # Should remove TODO call and result (indices 1-2), keep everything else
        self.assertEqual(len(result), 4)
        self.assertEqual(result[0].content, "Message 1")
        self.assertEqual(result[1].content, "Middle")
        self.assertEqual(result[2].content, "Recent 1")
        self.assertEqual(result[3].content, "Recent 2")

    def test_keeps_todos_in_retention_window(self):
        """Test that cleaner preserves TODOs within retention window."""
        messages = [
            UserMessage(content="Message 1", session_id="test", sequence=0),
            ToolCallMessage(
                tool_calls=[ToolCall(id="todo_1", tool_name="todo_write", arguments={})],
                session_id="test",
                sequence=1
            ),
            ToolResultObservation(
                call_id="todo_1",
                content="TODO updated",
                session_id="test",
                sequence=2
            ),
        ]

        # Retention window of 10 means all messages are protected
        result = self.cleaner.clean(messages, retention_window=10)

        # Should keep all messages (all within retention window)
        self.assertEqual(len(result), 3)

    def test_multiple_todos(self):
        """Test cleaner with multiple TODO updates."""
        messages = [
            # Old TODO (should be removed)
            ToolCallMessage(
                tool_calls=[ToolCall(id="todo_1", tool_name="todo_write", arguments={})],
                session_id="test",
                sequence=0
            ),
            ToolResultObservation(call_id="todo_1", content="TODO 1", session_id="test", sequence=1),
            # Middle message
            LLMRespondMessage(content="Middle", session_id="test", sequence=2),
            # Old TODO (should be removed)
            ToolCallMessage(
                tool_calls=[ToolCall(id="todo_2", tool_name="todo_write", arguments={})],
                session_id="test",
                sequence=3
            ),
            ToolResultObservation(call_id="todo_2", content="TODO 2", session_id="test", sequence=4),
            # Recent TODO (should be kept)
            ToolCallMessage(
                tool_calls=[ToolCall(id="todo_3", tool_name="todo_write", arguments={})],
                session_id="test",
                sequence=5
            ),
            ToolResultObservation(call_id="todo_3", content="TODO 3", session_id="test", sequence=6),
        ]

        # Retention window of 2 protects last 2 messages (recent TODO)
        result = self.cleaner.clean(messages, retention_window=2)

        # Should keep: Middle + recent TODO (indices 2, 5, 6)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0].content, "Middle")
        self.assertIsInstance(result[1], ToolCallMessage)
        self.assertIsInstance(result[2], ToolResultObservation)
        self.assertEqual(result[2].content, "TODO 3")

    def test_non_todo_tool_calls_preserved(self):
        """Test that non-TODO tool calls are not removed."""
        messages = [
            ToolCallMessage(
                tool_calls=[ToolCall(id="read_1", tool_name="read_file", arguments={})],
                session_id="test",
                sequence=0
            ),
            ToolResultObservation(call_id="read_1", content="File content", session_id="test", sequence=1),
            LLMRespondMessage(content="Recent", session_id="test", sequence=2),
        ]

        result = self.cleaner.clean(messages, retention_window=1)

        # Should keep all messages (read_file is not todo_write)
        self.assertEqual(len(result), 3)


class TestDuplicateCleaner(unittest.TestCase):
    """Test DuplicateCleaner functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.cleaner = DuplicateCleaner()

    def test_empty_messages(self):
        """Test that cleaner handles empty message list."""
        result = self.cleaner.clean([], retention_window=10)
        self.assertEqual(result, [])

    def test_single_message(self):
        """Test that cleaner handles single message."""
        messages = [UserMessage(content="Hello", session_id="test", sequence=0)]
        result = self.cleaner.clean(messages, retention_window=10)
        self.assertEqual(len(result), 1)

    def test_no_duplicates(self):
        """Test that cleaner leaves unique messages unchanged."""
        messages = [
            UserMessage(content="Message 1", session_id="test", sequence=0),
            UserMessage(content="Message 2", session_id="test", sequence=1),
            UserMessage(content="Message 3", session_id="test", sequence=2),
        ]

        result = self.cleaner.clean(messages, retention_window=10)
        self.assertEqual(len(result), 3)
        self.assertEqual(result, messages)

    def test_removes_consecutive_duplicates(self):
        """Test that cleaner removes consecutive duplicate messages."""
        messages = [
            UserMessage(content="Hello", session_id="test", sequence=0),
            UserMessage(content="Hello", session_id="test", sequence=1),
            UserMessage(content="World", session_id="test", sequence=2),
            UserMessage(content="World", session_id="test", sequence=3),
            UserMessage(content="End", session_id="test", sequence=4),
        ]

        result = self.cleaner.clean(messages, retention_window=10)

        # Should remove duplicates at indices 1 and 3
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0].content, "Hello")
        self.assertEqual(result[1].content, "World")
        self.assertEqual(result[2].content, "End")

    def test_respects_retention_window(self):
        """Test that cleaner preserves duplicates in retention window."""
        messages = [
            UserMessage(content="Hello", session_id="test", sequence=0),
            UserMessage(content="Hello", session_id="test", sequence=1),
            UserMessage(content="World", session_id="test", sequence=2),
            UserMessage(content="World", session_id="test", sequence=3),
        ]

        # Retention window of 2 protects last 2 messages
        result = self.cleaner.clean(messages, retention_window=2)

        # Should only remove duplicate at index 1 (outside retention window)
        # Index 3 is within retention window so kept
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0].content, "Hello")
        self.assertEqual(result[1].content, "World")
        self.assertEqual(result[2].content, "World")

    def test_different_message_types_not_duplicates(self):
        """Test that different message types are not considered duplicates."""
        messages = [
            UserMessage(content="Hello", session_id="test", sequence=0),
            LLMRespondMessage(content="Hello", session_id="test", sequence=1),
            UserMessage(content="World", session_id="test", sequence=2),
        ]

        result = self.cleaner.clean(messages, retention_window=10)

        # Should keep all (different types, even with same content)
        self.assertEqual(len(result), 3)

    def test_messages_without_content(self):
        """Test handling of messages without content field."""
        messages = [
            ToolCallMessage(
                tool_calls=[ToolCall(id="call_1", tool_name="test", arguments={})],
                session_id="test",
                sequence=0
            ),
            ToolCallMessage(
                tool_calls=[ToolCall(id="call_1", tool_name="test", arguments={})],
                session_id="test",
                sequence=1
            ),
        ]

        result = self.cleaner.clean(messages, retention_window=10)

        # Should keep all (no content field to compare)
        self.assertEqual(len(result), 2)


class TestCompositeCleaner(unittest.TestCase):
    """Test CompositeCleaner functionality."""

    def test_empty_cleaners_list(self):
        """Test that composite with no cleaners returns messages unchanged."""
        cleaner = CompositeCleaner([])
        messages = [
            UserMessage(content="Hello", session_id="test", sequence=0),
        ]

        result = cleaner.clean(messages, retention_window=10)
        self.assertEqual(result, messages)

    def test_single_cleaner(self):
        """Test that composite with single cleaner works."""
        cleaner = CompositeCleaner([DuplicateCleaner()])
        messages = [
            UserMessage(content="Hello", session_id="test", sequence=0),
            UserMessage(content="Hello", session_id="test", sequence=1),
        ]

        result = cleaner.clean(messages, retention_window=10)
        self.assertEqual(len(result), 1)

    def test_multiple_cleaners(self):
        """Test that composite applies multiple cleaners in sequence."""
        cleaner = CompositeCleaner([TODOCleaner(), DuplicateCleaner()])

        messages = [
            # Duplicate user messages
            UserMessage(content="Hello", session_id="test", sequence=0),
            UserMessage(content="Hello", session_id="test", sequence=1),
            # Old TODO
            ToolCallMessage(
                tool_calls=[ToolCall(id="todo_1", tool_name="todo_write", arguments={})],
                session_id="test",
                sequence=2
            ),
            ToolResultObservation(call_id="todo_1", content="TODO", session_id="test", sequence=3),
            # Recent message
            UserMessage(content="Recent", session_id="test", sequence=4),
        ]

        result = cleaner.clean(messages, retention_window=1)

        # Should remove:
        # - Duplicate "Hello" at index 1 (DuplicateCleaner)
        # - TODO messages at indices 2-3 (TODOCleaner, outside retention window)
        # Should keep: Hello (first), Recent
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].content, "Hello")
        self.assertEqual(result[1].content, "Recent")


class TestMessageCleanerIntegration(unittest.TestCase):
    """Test MessageCleaner integration with HistoryManager."""

    def test_history_manager_uses_todo_cleaner_by_default(self):
        """Test that HistoryManager auto-configures TODOCleaner when auto_remove_old_todos=True."""
        from agent_framework.memory.history import HistoryManager
        from agent_framework.memory.summarizer import SimpleSummarizer

        history = HistoryManager(
            summarizer=SimpleSummarizer(),
            max_tokens=1000,
            auto_remove_old_todos=True
        )

        # Should have one cleaner (TODOCleaner)
        self.assertEqual(len(history.message_cleaners), 1)
        self.assertIsInstance(history.message_cleaners[0], TODOCleaner)

    def test_history_manager_no_cleaners_when_disabled(self):
        """Test that HistoryManager has no cleaners when auto_remove_old_todos=False."""
        from agent_framework.memory.history import HistoryManager
        from agent_framework.memory.summarizer import SimpleSummarizer

        history = HistoryManager(
            summarizer=SimpleSummarizer(),
            max_tokens=1000,
            auto_remove_old_todos=False
        )

        # Should have no cleaners
        self.assertEqual(len(history.message_cleaners), 0)

    def test_history_manager_custom_cleaners(self):
        """Test that HistoryManager accepts custom cleaners."""
        from agent_framework.memory.history import HistoryManager
        from agent_framework.memory.summarizer import SimpleSummarizer

        custom_cleaners = [DuplicateCleaner(), TODOCleaner()]

        history = HistoryManager(
            summarizer=SimpleSummarizer(),
            max_tokens=1000,
            message_cleaners=custom_cleaners
        )

        # Should have the custom cleaners
        self.assertEqual(len(history.message_cleaners), 2)
        self.assertIsInstance(history.message_cleaners[0], DuplicateCleaner)
        self.assertIsInstance(history.message_cleaners[1], TODOCleaner)

    def test_history_manager_cleaners_applied_on_add(self):
        """Test that cleaners are applied when adding messages to history."""
        from agent_framework.memory.history import HistoryManager
        from agent_framework.memory.summarizer import SimpleSummarizer

        history = HistoryManager(
            summarizer=SimpleSummarizer(),
            max_tokens=1000,
            retention_window=2,
            auto_remove_old_todos=True
        )

        # Add messages including old TODO
        history.add(UserMessage(content="Start", session_id="test", sequence=0))
        history.add(ToolCallMessage(
            tool_calls=[ToolCall(id="todo_1", tool_name="todo_write", arguments={})],
            session_id="test",
            sequence=1
        ))
        history.add(ToolResultObservation(call_id="todo_1", content="TODO 1", session_id="test", sequence=2))
        history.add(UserMessage(content="Middle", session_id="test", sequence=3))
        history.add(UserMessage(content="Recent", session_id="test", sequence=4))

        # Add new TODO - should trigger cleaner to remove old TODO
        history.add(ToolCallMessage(
            tool_calls=[ToolCall(id="todo_2", tool_name="todo_write", arguments={})],
            session_id="test",
            sequence=5
        ))
        history.add(ToolResultObservation(call_id="todo_2", content="TODO 2", session_id="test", sequence=6))

        # Old TODO should be removed (outside retention window of 2)
        messages = history.get_messages()

        # Debug: print what we actually have
        print(f"\nActual messages ({len(messages)}):")
        for i, msg in enumerate(messages):
            content = getattr(msg, 'content', f"<{type(msg).__name__}>")
            print(f"  [{i}] {type(msg).__name__}: {content}")

        # Should have: Start, Middle, Recent, new TODO call, new TODO result
        self.assertEqual(len(messages), 5)
        self.assertEqual(messages[0].content, "Start")
        self.assertEqual(messages[1].content, "Middle")
        self.assertEqual(messages[2].content, "Recent")
        self.assertIsInstance(messages[3], ToolCallMessage)
        self.assertIsInstance(messages[4], ToolResultObservation)


if __name__ == '__main__':
    unittest.main(verbosity=2)
