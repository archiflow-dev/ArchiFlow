"""Tests for automatic TODO removal in HistoryManager."""
import pytest
from agent_framework.memory import HistoryManager, SimpleSummarizer
from agent_framework.messages.types import (
    UserMessage, SystemMessage, ToolCallMessage, ToolResultObservation, ToolCall
)


class TestTodoRemoval:
    """Test automatic removal of old TODO messages."""

    def test_basic_todo_removal(self):
        """Test that old TODOs are removed when new TODO is added."""
        history = HistoryManager(
            summarizer=SimpleSummarizer(),
            max_tokens=100000,
            retention_window=5,
            auto_remove_old_todos=True
        )

        # Add initial messages
        history.add(SystemMessage(content="System", session_id="test", sequence=0))
        history.add(UserMessage(content="User request", session_id="test", sequence=1))

        # Add first TODO
        todo_call_1 = ToolCallMessage(
            tool_calls=[ToolCall(
                id="call_1",
                tool_name="todo_write",
                arguments={"todos": [{"content": "Task 1", "status": "pending"}]}
            )],
            session_id="test",
            sequence=2
        )
        history.add(todo_call_1)

        todo_result_1 = ToolResultObservation(
            call_id="call_1",
            content="TODO updated: Task 1 (pending)",
            session_id="test",
            sequence=3
        )
        history.add(todo_result_1)

        assert len(history.messages) == 4  # System, User, TodoCall, TodoResult

        # Add some other messages to move TODO outside retention window
        # With new MessageCleaner, TODOs are removed as soon as they're fully outside retention
        for i in range(6):
            history.add(UserMessage(content=f"Message {i}", session_id="test", sequence=4 + i))

        # After adding 6 messages, the old TODO should have been removed automatically
        # (both call and result were outside retention window of 5)
        assert len(history.messages) == 8  # System, User, 6 messages (TODO removed)

        # Add second TODO
        todo_call_2 = ToolCallMessage(
            tool_calls=[ToolCall(
                id="call_2",
                tool_name="todo_write",
                arguments={"todos": [{"content": "Task 2", "status": "in_progress"}]}
            )],
            session_id="test",
            sequence=10
        )
        history.add(todo_call_2)

        todo_result_2 = ToolResultObservation(
            call_id="call_2",
            content="TODO updated: Task 2 (in_progress)",
            session_id="test",
            sequence=11
        )
        history.add(todo_result_2)

        # Old TODO should be removed (call_1 and result_1)
        # New count: System(1) + User(1) + 6 messages + TodoCall2 + TodoResult2 = 10
        assert len(history.messages) == 10

        # Verify old TODO is gone
        todo_call_ids = []
        for msg in history.messages:
            if isinstance(msg, ToolCallMessage):
                for tc in msg.tool_calls:
                    if tc.tool_name == "todo_write":
                        todo_call_ids.append(tc.id)

        assert "call_1" not in todo_call_ids
        assert "call_2" in todo_call_ids

    def test_todo_removal_respects_retention_window(self):
        """Test that TODOs within retention window are kept."""
        history = HistoryManager(
            summarizer=SimpleSummarizer(),
            max_tokens=100000,
            retention_window=10,
            auto_remove_old_todos=True
        )

        # Add initial message
        history.add(UserMessage(content="Start", session_id="test", sequence=0))

        # Add first TODO
        todo_call_1 = ToolCallMessage(
            tool_calls=[ToolCall(
                id="call_1",
                tool_name="todo_write",
                arguments={"todos": [{"content": "Task 1", "status": "pending"}]}
            )],
            session_id="test",
            sequence=1
        )
        history.add(todo_call_1)

        todo_result_1 = ToolResultObservation(
            call_id="call_1",
            content="TODO 1",
            session_id="test",
            sequence=2
        )
        history.add(todo_result_1)

        # Add only 2 messages (TODO still in retention window of 10)
        history.add(UserMessage(content="Message 1", session_id="test", sequence=3))
        history.add(UserMessage(content="Message 2", session_id="test", sequence=4))

        assert len(history.messages) == 5

        # Add second TODO
        todo_call_2 = ToolCallMessage(
            tool_calls=[ToolCall(
                id="call_2",
                tool_name="todo_write",
                arguments={"todos": [{"content": "Task 2", "status": "in_progress"}]}
            )],
            session_id="test",
            sequence=5
        )
        history.add(todo_call_2)

        todo_result_2 = ToolResultObservation(
            call_id="call_2",
            content="TODO 2",
            session_id="test",
            sequence=6
        )
        history.add(todo_result_2)

        # First TODO should STILL be there (within retention window)
        # Count: Start + TodoCall1 + TodoResult1 + Msg1 + Msg2 + TodoCall2 + TodoResult2 = 7
        assert len(history.messages) == 7

        # Verify both TODOs are present
        todo_call_ids = []
        for msg in history.messages:
            if isinstance(msg, ToolCallMessage):
                for tc in msg.tool_calls:
                    if tc.tool_name == "todo_write":
                        todo_call_ids.append(tc.id)

        assert "call_1" in todo_call_ids  # Still in retention window
        assert "call_2" in todo_call_ids

    def test_todo_removal_disabled(self):
        """Test that TODOs are kept when auto_remove_old_todos=False."""
        history = HistoryManager(
            summarizer=SimpleSummarizer(),
            max_tokens=100000,
            retention_window=5,
            auto_remove_old_todos=False  # Disabled
        )

        # Add initial message
        history.add(UserMessage(content="Start", session_id="test", sequence=0))

        # Add first TODO
        todo_call_1 = ToolCallMessage(
            tool_calls=[ToolCall(
                id="call_1",
                tool_name="todo_write",
                arguments={"todos": [{"content": "Task 1", "status": "pending"}]}
            )],
            session_id="test",
            sequence=1
        )
        history.add(todo_call_1)

        todo_result_1 = ToolResultObservation(
            call_id="call_1",
            content="TODO 1",
            session_id="test",
            sequence=2
        )
        history.add(todo_result_1)

        # Add messages to move TODO outside retention window
        for i in range(6):
            history.add(UserMessage(content=f"Message {i}", session_id="test", sequence=3 + i))

        # Add second TODO
        todo_call_2 = ToolCallMessage(
            tool_calls=[ToolCall(
                id="call_2",
                tool_name="todo_write",
                arguments={"todos": [{"content": "Task 2", "status": "in_progress"}]}
            )],
            session_id="test",
            sequence=9
        )
        history.add(todo_call_2)

        todo_result_2 = ToolResultObservation(
            call_id="call_2",
            content="TODO 2",
            session_id="test",
            sequence=10
        )
        history.add(todo_result_2)

        # Both TODOs should still be present (removal disabled)
        # Count: Start + TodoCall1 + TodoResult1 + 6 messages + TodoCall2 + TodoResult2 = 11
        assert len(history.messages) == 11

        # Verify both TODOs are present
        todo_call_ids = []
        for msg in history.messages:
            if isinstance(msg, ToolCallMessage):
                for tc in msg.tool_calls:
                    if tc.tool_name == "todo_write":
                        todo_call_ids.append(tc.id)

        assert "call_1" in todo_call_ids
        assert "call_2" in todo_call_ids

    def test_multiple_todos_removed(self):
        """Test that multiple old TODOs are removed when they're outside retention window."""
        history = HistoryManager(
            summarizer=SimpleSummarizer(),
            max_tokens=100000,
            retention_window=3,  # Small retention window for easier testing
            auto_remove_old_todos=True
        )

        # Add initial message
        history.add(UserMessage(content="Start", session_id="test", sequence=0))

        # Add first TODO
        todo_call_1 = ToolCallMessage(
            tool_calls=[ToolCall(
                id="call_1",
                tool_name="todo_write",
                arguments={"todos": [{"content": "Task 1", "status": "pending"}]}
            )],
            session_id="test",
            sequence=1
        )
        history.add(todo_call_1)

        todo_result_1 = ToolResultObservation(
            call_id="call_1",
            content="TODO 1",
            session_id="test",
            sequence=2
        )
        history.add(todo_result_1)

        # Add spacing to push TODO 1 outside retention window
        for i in range(5):
            history.add(UserMessage(content=f"Message {i}", session_id="test", sequence=3 + i))

        # Add second TODO - should remove TODO 1
        todo_call_2 = ToolCallMessage(
            tool_calls=[ToolCall(
                id="call_2",
                tool_name="todo_write",
                arguments={"todos": [{"content": "Task 2", "status": "in_progress"}]}
            )],
            session_id="test",
            sequence=8
        )
        history.add(todo_call_2)

        todo_result_2 = ToolResultObservation(
            call_id="call_2",
            content="TODO 2",
            session_id="test",
            sequence=9
        )
        history.add(todo_result_2)

        # Verify TODO 1 is removed, TODO 2 remains
        todo_call_ids = []
        for msg in history.messages:
            if isinstance(msg, ToolCallMessage):
                for tc in msg.tool_calls:
                    if tc.tool_name == "todo_write":
                        todo_call_ids.append(tc.id)

        assert "call_1" not in todo_call_ids  # Removed (outside retention window)
        assert "call_2" in todo_call_ids      # Just added

    def test_non_todo_messages_unaffected(self):
        """Test that non-TODO tool calls are not affected."""
        history = HistoryManager(
            summarizer=SimpleSummarizer(),
            max_tokens=100000,
            retention_window=5,
            auto_remove_old_todos=True
        )

        # Add various non-TODO messages
        history.add(UserMessage(content="Start", session_id="test", sequence=0))

        # Add a non-TODO tool call
        other_call = ToolCallMessage(
            tool_calls=[ToolCall(
                id="other_1",
                tool_name="read_file",
                arguments={"path": "test.py"}
            )],
            session_id="test",
            sequence=1
        )
        history.add(other_call)

        other_result = ToolResultObservation(
            call_id="other_1",
            content="File contents",
            session_id="test",
            sequence=2
        )
        history.add(other_result)

        # Add TODO
        todo_call = ToolCallMessage(
            tool_calls=[ToolCall(
                id="todo_1",
                tool_name="todo_write",
                arguments={"todos": [{"content": "Task", "status": "pending"}]}
            )],
            session_id="test",
            sequence=3
        )
        history.add(todo_call)

        todo_result = ToolResultObservation(
            call_id="todo_1",
            content="TODO updated",
            session_id="test",
            sequence=4
        )
        history.add(todo_result)

        # Add spacing
        for i in range(6):
            history.add(UserMessage(content=f"Message {i}", session_id="test", sequence=5 + i))

        # Add another TODO
        todo_call_2 = ToolCallMessage(
            tool_calls=[ToolCall(
                id="todo_2",
                tool_name="todo_write",
                arguments={"todos": [{"content": "Task 2", "status": "in_progress"}]}
            )],
            session_id="test",
            sequence=11
        )
        history.add(todo_call_2)

        todo_result_2 = ToolResultObservation(
            call_id="todo_2",
            content="TODO 2",
            session_id="test",
            sequence=12
        )
        history.add(todo_result_2)

        # Verify non-TODO tool call is still present
        has_read_file = False
        for msg in history.messages:
            if isinstance(msg, ToolCallMessage):
                for tc in msg.tool_calls:
                    if tc.tool_name == "read_file":
                        has_read_file = True

        assert has_read_file, "Non-TODO tool call should not be removed"

    def test_empty_history(self):
        """Test that removal logic handles empty history gracefully."""
        history = HistoryManager(
            summarizer=SimpleSummarizer(),
            max_tokens=100000,
            retention_window=5,
            auto_remove_old_todos=True
        )

        # Add TODO to empty history (should not crash)
        todo_call = ToolCallMessage(
            tool_calls=[ToolCall(
                id="todo_1",
                tool_name="todo_write",
                arguments={"todos": [{"content": "Task", "status": "pending"}]}
            )],
            session_id="test",
            sequence=0
        )
        history.add(todo_call)

        todo_result = ToolResultObservation(
            call_id="todo_1",
            content="TODO updated",
            session_id="test",
            sequence=1
        )
        history.add(todo_result)

        # Should have 2 messages (no crash)
        assert len(history.messages) == 2

    def test_todo_with_error_result(self):
        """Test that TODO removal works even if TODO had an error."""
        history = HistoryManager(
            summarizer=SimpleSummarizer(),
            max_tokens=100000,
            retention_window=5,
            auto_remove_old_todos=True
        )

        history.add(UserMessage(content="Start", session_id="test", sequence=0))

        # Add TODO that resulted in error
        todo_call_1 = ToolCallMessage(
            tool_calls=[ToolCall(
                id="todo_1",
                tool_name="todo_write",
                arguments={"invalid": "data"}
            )],
            session_id="test",
            sequence=1
        )
        history.add(todo_call_1)

        # Error result (still a ToolResultObservation)
        todo_error = ToolResultObservation(
            call_id="todo_1",
            content="Error: Invalid TODO format",
            session_id="test",
            sequence=2
        )
        history.add(todo_error)

        # Add spacing
        for i in range(6):
            history.add(UserMessage(content=f"Message {i}", session_id="test", sequence=3 + i))

        # Add valid TODO
        todo_call_2 = ToolCallMessage(
            tool_calls=[ToolCall(
                id="todo_2",
                tool_name="todo_write",
                arguments={"todos": [{"content": "Task", "status": "pending"}]}
            )],
            session_id="test",
            sequence=9
        )
        history.add(todo_call_2)

        todo_result_2 = ToolResultObservation(
            call_id="todo_2",
            content="TODO updated",
            session_id="test",
            sequence=10
        )
        history.add(todo_result_2)

        # Error TODO should be removed
        todo_call_ids = []
        for msg in history.messages:
            if isinstance(msg, ToolCallMessage):
                for tc in msg.tool_calls:
                    if tc.tool_name == "todo_write":
                        todo_call_ids.append(tc.id)

        assert "todo_1" not in todo_call_ids
        assert "todo_2" in todo_call_ids
