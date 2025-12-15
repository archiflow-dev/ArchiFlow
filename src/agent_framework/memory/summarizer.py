"""
History Summarizer for compacting conversation history.
"""
from abc import ABC, abstractmethod
from typing import List, Optional
import logging

from ..messages.types import BaseMessage, UserMessage, ToolCallMessage, ToolResultObservation
from ..llm.provider import LLMProvider

logger = logging.getLogger(__name__)


class HistorySummarizer(ABC):
    """Base class for history summarization strategies."""

    @abstractmethod
    def summarize(self, messages: List[BaseMessage]) -> str:
        """
        Summarize a list of messages into a compact text representation.

        Args:
            messages: List of messages to summarize

        Returns:
            Summarized text representation
        """
        pass


class SimpleSummarizer(HistorySummarizer):
    """
    Simple summarizer that creates a basic text summary without LLM.

    This summarizer counts message types and creates a simple text description.
    """

    def summarize(self, messages: List[BaseMessage]) -> str:
        """
        Create a simple summary by counting message types and key actions.

        Args:
            messages: List of messages to summarize

        Returns:
            Text summary of the messages
        """
        if not messages:
            return "[No messages to summarize]"

        # Count message types
        user_messages = 0
        tool_calls = 0
        tool_results = 0
        tool_names = set()

        for msg in messages:
            if isinstance(msg, UserMessage):
                user_messages += 1
            elif isinstance(msg, ToolCallMessage):
                tool_calls += len(msg.tool_calls)
                for tc in msg.tool_calls:
                    tool_names.add(tc.tool_name)
            elif isinstance(msg, ToolResultObservation):
                tool_results += 1

        # Build summary
        summary_parts = []
        summary_parts.append(f"[Compacted {len(messages)} messages]")

        if user_messages > 0:
            summary_parts.append(f"{user_messages} user interaction(s)")

        if tool_calls > 0:
            tools_str = ", ".join(sorted(tool_names))
            summary_parts.append(f"{tool_calls} tool call(s): {tools_str}")

        return " | ".join(summary_parts)


class LLMSummarizer(HistorySummarizer):
    """
    LLM-based summarizer that uses an LLM to create intelligent summaries.

    This summarizer sends messages to an LLM with a specific prompt to create
    a concise summary of the conversation history.
    """

    SUMMARY_PROMPT = """You are a conversation history summarizer. Your task is to create a concise summary of the following conversation history.

Focus on:
1. Key user requests and goals
2. Important actions taken (files edited, commands run, etc.)
3. Significant results or findings
4. Current state or context

Be concise but preserve important details. Use bullet points if helpful.

Conversation to summarize:
{history}

Provide a brief summary (2-4 sentences or bullet points):"""

    def __init__(self, llm: LLMProvider, max_summary_tokens: int = 200):
        """
        Initialize LLM-based summarizer.

        Args:
            llm: LLM provider to use for summarization
            max_summary_tokens: Maximum tokens for the summary
        """
        self.llm = llm
        self.max_summary_tokens = max_summary_tokens

    def _format_messages_for_summary(self, messages: List[BaseMessage]) -> str:
        """
        Format messages into a readable text format for the LLM.

        Args:
            messages: List of messages to format

        Returns:
            Formatted text representation
        """
        lines = []

        for i, msg in enumerate(messages):
            if isinstance(msg, UserMessage):
                lines.append(f"User: {msg.content}")
            elif isinstance(msg, ToolCallMessage):
                for tc in msg.tool_calls:
                    lines.append(f"Agent called: {tc.tool_name}")
            elif isinstance(msg, ToolResultObservation):
                # Truncate long results
                content = msg.content[:200] + "..." if len(msg.content) > 200 else msg.content
                lines.append(f"Result: {content}")

        return "\n".join(lines)

    def summarize(self, messages: List[BaseMessage]) -> str:
        """
        Use LLM to create an intelligent summary of the messages.

        Args:
            messages: List of messages to summarize

        Returns:
            LLM-generated summary
        """
        if not messages:
            return "[No messages to summarize]"

        try:
            # Format messages into readable text
            history_text = self._format_messages_for_summary(messages)

            # Create prompt
            prompt = self.SUMMARY_PROMPT.format(history=history_text)

            # Call LLM
            llm_messages = [
                {"role": "user", "content": prompt}
            ]

            response = self.llm.generate(
                llm_messages,
                max_tokens=self.max_summary_tokens
            )

            if response.content:
                summary = response.content.strip()
                logger.info(f"Generated LLM summary: {summary[:100]}...")
                return f"[Summary of {len(messages)} messages] {summary}"
            else:
                logger.warning("LLM returned empty summary, falling back to simple summary")
                return SimpleSummarizer().summarize(messages)

        except Exception as e:
            logger.error(f"Failed to generate LLM summary: {e}, falling back to simple summary")
            # Fallback to simple summarizer
            return SimpleSummarizer().summarize(messages)


class HybridSummarizer(HistorySummarizer):
    """
    Hybrid summarizer that uses simple summarization for small chunks
    and LLM summarization for larger chunks.
    """

    def __init__(self, llm: LLMProvider, threshold: int = 20, max_summary_tokens: int = 200):
        """
        Initialize hybrid summarizer.

        Args:
            llm: LLM provider to use for large summaries
            threshold: Number of messages above which to use LLM summarization
            max_summary_tokens: Maximum tokens for LLM summaries
        """
        self.simple_summarizer = SimpleSummarizer()
        self.llm_summarizer = LLMSummarizer(llm, max_summary_tokens)
        self.threshold = threshold

    def summarize(self, messages: List[BaseMessage]) -> str:
        """
        Choose between simple and LLM summarization based on message count.

        Args:
            messages: List of messages to summarize

        Returns:
            Summary using appropriate strategy
        """
        if len(messages) <= self.threshold:
            return self.simple_summarizer.summarize(messages)
        else:
            return self.llm_summarizer.summarize(messages)
