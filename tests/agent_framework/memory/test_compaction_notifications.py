"""
Tests for compaction notifications (Task 2.5).

Tests verify:
1. CompactionStartedMessage is published when compaction begins
2. CompactionCompleteMessage is published when compaction finishes
3. Notifications contain correct data
4. Notifications work for both compact() and compact_async()
5. No notifications when publish_callback is None
"""
import unittest
import asyncio
from typing import List
from agent_framework.memory.history import HistoryManager
from agent_framework.memory.summarizer import SimpleSummarizer
from agent_framework.messages.types import (
    BaseMessage,
    CompactionStartedMessage,
    CompactionCompleteMessage,
    UserMessage
)


class TestCompactionNotifications(unittest.TestCase):
    """Test compaction notification functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.summarizer = SimpleSummarizer()
        self.published_messages: List[BaseMessage] = []

    def publish_callback(self, message: BaseMessage):
        """Capture published messages for testing."""
        self.published_messages.append(message)

    def test_compaction_started_notification(self):
        """Test that CompactionStartedMessage is published when compaction begins."""
        history = HistoryManager(
            summarizer=self.summarizer,
            max_tokens=50000,  # High to avoid auto-compaction
            retention_window=3,
            publish_callback=self.publish_callback
        )

        # Add many messages
        for i in range(20):
            history.add(UserMessage(
                content=f"Message {i} " * 15,
                session_id="test",
                sequence=i
            ))

        # Compact
        history.compact()

        # Should have published CompactionStartedMessage
        started_messages = [
            msg for msg in self.published_messages
            if isinstance(msg, CompactionStartedMessage)
        ]
        self.assertEqual(len(started_messages), 1, "Expected one CompactionStartedMessage")

        # Verify message content
        started = started_messages[0]
        self.assertEqual(started.messages_count, 20)
        self.assertGreater(started.tokens_before, 0)
        self.assertGreater(started.utilization, 0.0)

    def test_compaction_complete_notification(self):
        """Test that CompactionCompleteMessage is published when compaction finishes."""
        history = HistoryManager(
            summarizer=self.summarizer,
            max_tokens=50000,
            retention_window=3,
            publish_callback=self.publish_callback
        )

        # Add many messages
        for i in range(20):
            history.add(UserMessage(
                content=f"Message {i} " * 15,
                session_id="test",
                sequence=i
            ))

        # Compact
        history.compact()

        # Should have published CompactionCompleteMessage
        complete_messages = [
            msg for msg in self.published_messages
            if isinstance(msg, CompactionCompleteMessage)
        ]
        self.assertEqual(len(complete_messages), 1, "Expected one CompactionCompleteMessage")

        # Verify message content
        complete = complete_messages[0]
        self.assertEqual(complete.messages_before, 20)
        self.assertLess(complete.messages_after, 20)  # Should have compacted
        self.assertGreater(complete.tokens_before, 0)
        self.assertGreater(complete.tokens_after, 0)
        self.assertLess(complete.tokens_after, complete.tokens_before)  # Should save tokens
        self.assertGreater(complete.time_elapsed, 0.0)
        self.assertEqual(complete.messages_compacted, complete.messages_before - complete.messages_after)
        self.assertEqual(complete.tokens_saved, complete.tokens_before - complete.tokens_after)

    def test_both_notifications_published(self):
        """Test that both started and complete notifications are published."""
        history = HistoryManager(
            summarizer=self.summarizer,
            max_tokens=50000,
            retention_window=3,
            publish_callback=self.publish_callback
        )

        # Add many messages
        for i in range(20):
            history.add(UserMessage(
                content=f"Message {i} " * 15,
                session_id="test",
                sequence=i
            ))

        # Compact
        history.compact()

        # Should have both types of notifications
        started_count = sum(
            1 for msg in self.published_messages
            if isinstance(msg, CompactionStartedMessage)
        )
        complete_count = sum(
            1 for msg in self.published_messages
            if isinstance(msg, CompactionCompleteMessage)
        )

        self.assertEqual(started_count, 1)
        self.assertEqual(complete_count, 1)

        # Started should come before complete
        started_idx = next(
            i for i, msg in enumerate(self.published_messages)
            if isinstance(msg, CompactionStartedMessage)
        )
        complete_idx = next(
            i for i, msg in enumerate(self.published_messages)
            if isinstance(msg, CompactionCompleteMessage)
        )
        self.assertLess(started_idx, complete_idx)

    def test_async_compaction_notifications(self):
        """Test that notifications work for async compaction."""
        async def run_test():
            history = HistoryManager(
                summarizer=self.summarizer,
                max_tokens=50000,
                retention_window=3,
                publish_callback=self.publish_callback
            )

            # Add many messages
            for i in range(20):
                history.add(UserMessage(
                    content=f"Message {i} " * 15,
                    session_id="test",
                    sequence=i
                ))

            # Compact asynchronously
            await history.compact_async()

            # Should have both types of notifications
            started_count = sum(
                1 for msg in self.published_messages
                if isinstance(msg, CompactionStartedMessage)
            )
            complete_count = sum(
                1 for msg in self.published_messages
                if isinstance(msg, CompactionCompleteMessage)
            )

            self.assertEqual(started_count, 1)
            self.assertEqual(complete_count, 1)

        asyncio.run(run_test())

    def test_no_notifications_when_callback_none(self):
        """Test that no notifications are published when publish_callback is None."""
        history = HistoryManager(
            summarizer=self.summarizer,
            max_tokens=50000,
            retention_window=3,
            publish_callback=None  # No callback
        )

        # Add many messages
        for i in range(20):
            history.add(UserMessage(
                content=f"Message {i} " * 15,
                session_id="test",
                sequence=i
            ))

        # Compact (should not raise error even without callback)
        history.compact()

        # No messages should have been published
        self.assertEqual(len(self.published_messages), 0)

    def test_notification_data_accuracy(self):
        """Test that notification data is accurate."""
        history = HistoryManager(
            summarizer=self.summarizer,
            max_tokens=50000,
            retention_window=3,
            publish_callback=self.publish_callback
        )

        # Add exactly 20 messages
        for i in range(20):
            history.add(UserMessage(
                content=f"Message {i} " * 15,
                session_id="test",
                sequence=i
            ))

        # Get state before compaction
        messages_before = len(history.messages)
        tokens_before = history.get_token_estimate()

        # Compact
        history.compact()

        # Get state after compaction
        messages_after = len(history.messages)
        tokens_after = history.get_token_estimate()

        # Find the complete notification
        complete = next(
            msg for msg in self.published_messages
            if isinstance(msg, CompactionCompleteMessage)
        )

        # Verify accuracy
        self.assertEqual(complete.messages_before, messages_before)
        self.assertEqual(complete.messages_after, messages_after)
        self.assertEqual(complete.tokens_before, tokens_before)
        self.assertEqual(complete.tokens_after, tokens_after)
        self.assertEqual(complete.messages_compacted, messages_before - messages_after)
        self.assertEqual(complete.tokens_saved, tokens_before - tokens_after)

    def test_notification_timing(self):
        """Test that time_elapsed is measured correctly."""
        history = HistoryManager(
            summarizer=self.summarizer,
            max_tokens=50000,
            retention_window=3,
            publish_callback=self.publish_callback
        )

        # Add many messages
        for i in range(20):
            history.add(UserMessage(
                content=f"Message {i} " * 15,
                session_id="test",
                sequence=i
            ))

        # Compact
        history.compact()

        # Find the complete notification
        complete = next(
            msg for msg in self.published_messages
            if isinstance(msg, CompactionCompleteMessage)
        )

        # Time should be positive and reasonable (< 1 second for SimpleSummarizer)
        self.assertGreater(complete.time_elapsed, 0.0)
        self.assertLess(complete.time_elapsed, 1.0)

    def test_notification_session_id(self):
        """Test that notification uses correct session_id."""
        history = HistoryManager(
            summarizer=self.summarizer,
            max_tokens=50000,
            retention_window=3,
            publish_callback=self.publish_callback
        )

        # Add messages with specific session_id
        session_id = "test_session_123"
        for i in range(20):
            history.add(UserMessage(
                content=f"Message {i} " * 15,
                session_id=session_id,
                sequence=i
            ))

        # Compact
        history.compact()

        # All notifications should have the correct session_id
        for msg in self.published_messages:
            self.assertEqual(msg.session_id, session_id)


if __name__ == '__main__':
    unittest.main(verbosity=2)
