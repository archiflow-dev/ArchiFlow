"""
Compaction strategies for managing conversation history.

This module provides strategies for determining which messages to preserve
and which to summarize during history compaction.
"""
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List

from ..messages.types import (
    BaseMessage,
    BatchToolResultObservation,
    SystemMessage,
    ToolCallMessage,
    ToolResultObservation,
    UserMessage,
)

logger = logging.getLogger(__name__)


@dataclass
class CompactionAnalysis:
    """Result of analyzing which messages to preserve vs. summarize.

    Attributes:
        preserved_head: Messages to keep at the beginning (anchors)
        middle_chunk: Messages to summarize or drop
        preserved_tail: Recent messages to keep at the end (working context)
    """
    preserved_head: List[BaseMessage]
    middle_chunk: List[BaseMessage]
    preserved_tail: List[BaseMessage]


class CompactionStrategy(ABC):
    """Base class for history compaction strategies.

    A compaction strategy determines which messages to preserve
    and which to summarize when conversation history exceeds limits.
    """

    @abstractmethod
    def analyze(
        self,
        messages: List[BaseMessage],
        retention_window: int
    ) -> CompactionAnalysis:
        """Analyze messages and determine what to preserve.

        Args:
            messages: Full list of messages to analyze
            retention_window: Number of recent messages to preserve

        Returns:
            CompactionAnalysis with preserved and summarizable messages
        """
        pass


class SelectiveRetentionStrategy(CompactionStrategy):
    """Selective Retention (Anchor Method) compaction strategy.

    Preserves:
    1. System Message (if at index 0)
    2. First User Message (the initial goal)
    3. Last N messages (working context)
    4. Tool calls for any tool results in the tail (prevents orphans)

    Summarizes:
    - The middle chunk between head and tail

    This is the default strategy used by ArchiFlow agents.
    """

    def analyze(
        self,
        messages: List[BaseMessage],
        retention_window: int
    ) -> CompactionAnalysis:
        """Analyze messages using selective retention approach.

        Args:
            messages: Full list of messages to analyze
            retention_window: Number of recent messages to preserve

        Returns:
            CompactionAnalysis with preserved head, middle, and tail
        """
        if len(messages) <= retention_window + 2:
            # Not enough messages to compact
            return CompactionAnalysis(
                preserved_head=messages,
                middle_chunk=[],
                preserved_tail=[]
            )

        preserved_head = []
        preserved_tail = []
        middle_chunk = []

        # 1. Identify Head (System + Goal)
        idx = 0

        # Keep first SystemMessage if present
        if idx < len(messages) and isinstance(messages[idx], SystemMessage):
            preserved_head.append(messages[idx])
            idx += 1

        # Keep first UserMessage (Goal) if present
        # Scan forward up to 5 messages to find the first user message
        found_goal = False
        temp_idx = idx
        while temp_idx < len(messages) and temp_idx < 5:
            if isinstance(messages[temp_idx], UserMessage):
                # Include everything from idx to this UserMessage
                preserved_head.extend(messages[idx:temp_idx + 1])
                idx = temp_idx + 1
                found_goal = True
                break
            temp_idx += 1

        if not found_goal:
            # If no user message found early, keep the next message as part of head
            end_head = min(idx + 1, len(messages))
            preserved_head.extend(messages[idx:end_head])
            idx = end_head

        # 2. Identify Tail (Last N messages)
        tail_start = max(idx, len(messages) - retention_window)
        preserved_tail = messages[tail_start:]

        # 2.5. Extend tail backwards to include tool_calls for any tool results
        # This prevents orphaned tool results (tool results without their tool_calls)
        call_ids_needed = set()

        # Collect all tool_call_ids referenced by tool results in the tail
        for msg in preserved_tail:
            if isinstance(msg, ToolResultObservation):
                call_ids_needed.add(msg.call_id)
            elif isinstance(msg, BatchToolResultObservation):
                for result in msg.results:
                    call_ids_needed.add(result.call_id)

        # Walk backwards from tail_start to find messages with needed tool_calls
        if call_ids_needed:
            extended_start = tail_start
            for i in range(tail_start - 1, idx - 1, -1):
                msg = messages[i]
                if isinstance(msg, ToolCallMessage):
                    # Check if this message has any of the needed tool calls
                    has_needed_call = any(tc.id in call_ids_needed for tc in msg.tool_calls)
                    if has_needed_call:
                        extended_start = i
                        # Remove the call_ids we found
                        for tc in msg.tool_calls:
                            call_ids_needed.discard(tc.id)

                        # If we found all needed calls, we can stop
                        if not call_ids_needed:
                            break

            # Update tail to include the extended range
            if extended_start < tail_start:
                preserved_tail = messages[extended_start:]
                tail_start = extended_start

        # 3. Identify Middle (to be summarized)
        if tail_start > idx:
            middle_chunk = messages[idx:tail_start]

        logger.debug(
            f"Compaction analysis: head={len(preserved_head)}, "
            f"middle={len(middle_chunk)}, tail={len(preserved_tail)}"
        )

        return CompactionAnalysis(
            preserved_head=preserved_head,
            middle_chunk=middle_chunk,
            preserved_tail=preserved_tail
        )


class SlidingWindowStrategy(CompactionStrategy):
    """Sliding Window compaction strategy.

    Preserves:
    - Last N messages only (no head anchors)
    - Tool calls for any tool results in the window

    Summarizes:
    - Everything before the window

    This is a simpler strategy that may be useful for:
    - Chat-like interactions without a fixed goal
    - Workflows where only recent context matters
    - Debugging/testing scenarios
    """

    def analyze(
        self,
        messages: List[BaseMessage],
        retention_window: int
    ) -> CompactionAnalysis:
        """Analyze messages using sliding window approach.

        Args:
            messages: Full list of messages to analyze
            retention_window: Number of recent messages to preserve

        Returns:
            CompactionAnalysis with empty head, middle, and preserved tail
        """
        if len(messages) <= retention_window:
            # Not enough messages to compact
            return CompactionAnalysis(
                preserved_head=[],
                middle_chunk=[],
                preserved_tail=messages
            )

        # Start with last N messages
        tail_start = len(messages) - retention_window
        preserved_tail = messages[tail_start:]

        # Extend tail backwards to include tool_calls for any tool results
        call_ids_needed = set()

        # Collect all tool_call_ids referenced by tool results in the tail
        for msg in preserved_tail:
            if isinstance(msg, ToolResultObservation):
                call_ids_needed.add(msg.call_id)
            elif isinstance(msg, BatchToolResultObservation):
                for result in msg.results:
                    call_ids_needed.add(result.call_id)

        # Walk backwards from tail_start to find messages with needed tool_calls
        if call_ids_needed:
            extended_start = tail_start
            for i in range(tail_start - 1, -1, -1):
                msg = messages[i]
                if isinstance(msg, ToolCallMessage):
                    # Check if this message has any of the needed tool calls
                    has_needed_call = any(tc.id in call_ids_needed for tc in msg.tool_calls)
                    if has_needed_call:
                        extended_start = i
                        # Remove the call_ids we found
                        for tc in msg.tool_calls:
                            call_ids_needed.discard(tc.id)

                        # If we found all needed calls, we can stop
                        if not call_ids_needed:
                            break

            # Update tail to include the extended range
            if extended_start < tail_start:
                preserved_tail = messages[extended_start:]
                tail_start = extended_start

        # Everything before the tail is the middle chunk (to be summarized)
        middle_chunk = messages[:tail_start] if tail_start > 0 else []

        logger.debug(
            f"Sliding window analysis: "
            f"middle={len(middle_chunk)}, tail={len(preserved_tail)}"
        )

        return CompactionAnalysis(
            preserved_head=[],
            middle_chunk=middle_chunk,
            preserved_tail=preserved_tail
        )
