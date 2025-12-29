"""
Message cleaners for preprocessing conversation history.

This module provides pluggable message cleaners that can remove or modify
messages before they are stored in history or used for compaction.
"""
import logging
from abc import ABC, abstractmethod
from typing import List, Set

from ..messages.types import (
    BaseMessage,
    ToolCallMessage,
    ToolResultObservation,
)

logger = logging.getLogger(__name__)


class MessageCleaner(ABC):
    """Base class for message cleanup plugins.

    Message cleaners are applied to the message history to remove or modify
    messages according to specific rules (e.g., removing old TODOs, duplicates).
    """

    @abstractmethod
    def clean(
        self,
        messages: List[BaseMessage],
        retention_window: int
    ) -> List[BaseMessage]:
        """Clean messages according to the cleaner's rules.

        Args:
            messages: Full list of messages to clean
            retention_window: Number of recent messages to protect from cleaning

        Returns:
            Cleaned list of messages (may have fewer items than input)
        """
        pass


class TODOCleaner(MessageCleaner):
    """Removes old TODO-related messages from history.

    This cleaner removes previous TODO tool calls and results when new TODOs
    are added, keeping only the most recent TODO state. This prevents
    accumulation of obsolete TODO lists in the conversation history.

    Respects the retention window - only removes TODOs outside of it.
    """

    def clean(
        self,
        messages: List[BaseMessage],
        retention_window: int
    ) -> List[BaseMessage]:
        """Remove old TODO messages while preserving recent ones.

        Args:
            messages: Full list of messages to clean
            retention_window: Number of recent messages to protect

        Returns:
            Cleaned list with old TODOs removed
        """
        if len(messages) == 0:
            return messages

        # Find all TODO-related message indices
        todo_indices = self._find_todo_indices(messages)

        if len(todo_indices) == 0:
            return messages

        # Calculate retention boundary
        retention_start = max(0, len(messages) - retention_window)

        # Find which TODO pairs to keep (avoid orphaned results/calls)
        # A TODO pair should be removed only if BOTH call and result are outside retention
        call_ids_to_keep = set()
        call_ids_to_remove = set()

        # First, find all TODO results in retention window - keep their calls
        for idx in todo_indices:
            if idx >= retention_start:  # In retention window
                msg = messages[idx]
                if isinstance(msg, ToolResultObservation):
                    call_ids_to_keep.add(msg.call_id)

        # Now determine which calls to remove
        for idx in todo_indices:
            msg = messages[idx]
            if isinstance(msg, ToolCallMessage):
                for tc in msg.tool_calls:
                    if tc.tool_name == "todo_write":
                        if idx < retention_start and tc.id not in call_ids_to_keep:
                            call_ids_to_remove.add(tc.id)

        # Collect indices to remove (calls and results for call_ids_to_remove only)
        indices_to_remove = set()
        for idx in todo_indices:
            msg = messages[idx]
            if isinstance(msg, ToolCallMessage):
                for tc in msg.tool_calls:
                    if tc.tool_name == "todo_write" and tc.id in call_ids_to_remove:
                        indices_to_remove.add(idx)
                        break
            elif isinstance(msg, ToolResultObservation):
                if msg.call_id in call_ids_to_remove:
                    indices_to_remove.add(idx)

        if len(indices_to_remove) == 0:
            return messages

        # Build cleaned message list (exclude removed indices)
        cleaned_messages = [
            msg for i, msg in enumerate(messages)
            if i not in indices_to_remove
        ]

        logger.info(
            f"TODOCleaner removed {len(indices_to_remove)} old TODO message(s) "
            f"(kept {len(todo_indices) - len(indices_to_remove)} in retention window)"
        )

        return cleaned_messages

    def _find_todo_indices(self, messages: List[BaseMessage]) -> List[int]:
        """Find indices of all TODO-related messages.

        Args:
            messages: List of messages to search

        Returns:
            List of indices for TODO tool calls and results
        """
        todo_indices = []

        for i, msg in enumerate(messages):
            if self._is_todo_related_message(msg, messages, i):
                todo_indices.append(i)

        return todo_indices

    def _is_todo_related_message(
        self,
        msg: BaseMessage,
        messages: List[BaseMessage],
        idx: int
    ) -> bool:
        """Check if a message is related to TODO (either a tool_call or tool_result).

        Args:
            msg: Message to check
            messages: Full message list (for searching backwards)
            idx: Index of the message in the list

        Returns:
            True if the message is a todo_write call or its result
        """
        # Check if it's a ToolCallMessage with todo_write
        if isinstance(msg, ToolCallMessage):
            return any(tc.tool_name == "todo_write" for tc in msg.tool_calls)

        # Check if it's a ToolResultObservation for a todo_write call
        if isinstance(msg, ToolResultObservation):
            # Search backwards for the corresponding tool_call
            for i in range(idx - 1, -1, -1):
                if isinstance(messages[i], ToolCallMessage):
                    for tc in messages[i].tool_calls:
                        if tc.id == msg.call_id and tc.tool_name == "todo_write":
                            return True

        return False


class DuplicateCleaner(MessageCleaner):
    """Removes duplicate messages from history.

    This cleaner removes consecutive duplicate messages (same type and content)
    to reduce redundancy in the conversation history.

    Respects the retention window - only removes duplicates outside of it.
    """

    def clean(
        self,
        messages: List[BaseMessage],
        retention_window: int
    ) -> List[BaseMessage]:
        """Remove duplicate consecutive messages.

        Args:
            messages: Full list of messages to clean
            retention_window: Number of recent messages to protect

        Returns:
            Cleaned list with duplicates removed
        """
        if len(messages) <= 1:
            return messages

        # Calculate retention boundary
        # If retention_window >= len(messages), we can still remove duplicates
        # Only protect if we have a meaningful retention window
        if retention_window < len(messages):
            retention_start = len(messages) - retention_window
        else:
            # Retention window covers all messages, still remove duplicates
            # but be conservative - protect nothing (remove all duplicates)
            retention_start = len(messages)

        # Collect indices to remove
        indices_to_remove: Set[int] = set()

        # Check all consecutive pairs
        for i in range(1, len(messages)):
            # Only remove if the duplicate is outside retention window
            if i < retention_start and self._is_duplicate(messages[i - 1], messages[i]):
                indices_to_remove.add(i)

        if len(indices_to_remove) == 0:
            return messages

        # Build cleaned message list
        cleaned_messages = [
            msg for i, msg in enumerate(messages)
            if i not in indices_to_remove
        ]

        logger.info(
            f"DuplicateCleaner removed {len(indices_to_remove)} duplicate message(s)"
        )

        return cleaned_messages

    def _is_duplicate(self, msg1: BaseMessage, msg2: BaseMessage) -> bool:
        """Check if two messages are duplicates.

        Args:
            msg1: First message
            msg2: Second message

        Returns:
            True if messages are duplicates (same type and content)
        """
        # Must be same type
        if type(msg1) != type(msg2):
            return False

        # Compare content if available
        content1 = getattr(msg1, 'content', None)
        content2 = getattr(msg2, 'content', None)

        if content1 is not None and content2 is not None:
            return content1 == content2

        # For messages without content field, consider them non-duplicate
        return False


class CompositeCleaner(MessageCleaner):
    """Applies multiple cleaners in sequence.

    This cleaner allows combining multiple cleaning strategies by applying
    them one after another in the specified order.
    """

    def __init__(self, cleaners: List[MessageCleaner]):
        """Initialize composite cleaner.

        Args:
            cleaners: List of cleaners to apply in sequence
        """
        self.cleaners = cleaners

    def clean(
        self,
        messages: List[BaseMessage],
        retention_window: int
    ) -> List[BaseMessage]:
        """Apply all cleaners in sequence.

        Args:
            messages: Full list of messages to clean
            retention_window: Number of recent messages to protect

        Returns:
            Cleaned list after all cleaners have been applied
        """
        cleaned = messages

        for cleaner in self.cleaners:
            cleaned = cleaner.clean(cleaned, retention_window)

        return cleaned
