"""Accurate token counting for all LLM providers.

This module provides accurate token counting implementations for different
LLM providers, with fallback mechanisms for robustness.
"""

from typing import List, Dict, Optional, Protocol
import logging
import json

logger = logging.getLogger(__name__)


class TokenCounter(Protocol):
    """Protocol for token counting implementations."""

    def count_messages(self, messages: List[Dict]) -> int:
        """Count tokens in message list.

        Args:
            messages: List of message dictionaries in LLM format

        Returns:
            Total token count
        """
        ...

    def count_text(self, text: str) -> int:
        """Count tokens in text.

        Args:
            text: Text to count tokens for

        Returns:
            Token count
        """
        ...


class TiktokenCounter:
    """OpenAI-compatible token counter using tiktoken.

    Uses tiktoken library for accurate token counting that matches
    OpenAI's API token usage.
    """

    def __init__(self, model: str = "gpt-4"):
        """Initialize with model name.

        Args:
            model: Model name for encoding selection (e.g., "gpt-4", "gpt-3.5-turbo")
        """
        self.model = model
        self._encoding = None

    @property
    def encoding(self):
        """Lazy-load encoding to avoid startup overhead."""
        if self._encoding is None:
            try:
                import tiktoken
                self._encoding = tiktoken.encoding_for_model(self.model)
                logger.debug(f"Loaded tiktoken encoding for model: {self.model}")
            except ImportError:
                logger.warning(
                    "tiktoken library not installed. "
                    "Install with: pip install tiktoken"
                )
                return None
            except Exception as e:
                logger.warning(f"Failed to load tiktoken encoding: {e}")
                return None
        return self._encoding

    def count_messages(self, messages: List[Dict]) -> int:
        """Count tokens with tiktoken (most accurate).

        Implements OpenAI's token counting logic:
        - 3 tokens per message (formatting overhead)
        - 1 token per 'name' field
        - Actual content tokens via encoding
        - 3 tokens for reply priming

        Args:
            messages: List of message dictionaries

        Returns:
            Total token count
        """
        if self.encoding is None:
            return self._fallback_count_messages(messages)

        num_tokens = 0

        for message in messages:
            # Per-message overhead: 3 tokens
            num_tokens += 3

            for key, value in message.items():
                # Skip None values
                if value is None:
                    continue

                # Encode value
                try:
                    num_tokens += len(self.encoding.encode(str(value)))
                except Exception as e:
                    logger.warning(f"Failed to encode {key}: {e}")
                    # Fallback for this field
                    num_tokens += len(str(value)) // 4

                # Per-name overhead: 1 token
                if key == "name":
                    num_tokens += 1

            # Handle tool_calls
            if "tool_calls" in message and message["tool_calls"]:
                for tool_call in message["tool_calls"]:
                    try:
                        func_data = tool_call.get("function", {})
                        func_json = json.dumps(func_data)
                        num_tokens += len(self.encoding.encode(func_json))
                    except Exception as e:
                        logger.warning(f"Failed to encode tool_call: {e}")
                        # Fallback for this tool call
                        num_tokens += len(json.dumps(tool_call)) // 4

        # Final overhead: 3 tokens for assistant reply priming
        num_tokens += 3

        return num_tokens

    def count_text(self, text: str) -> int:
        """Count tokens in text.

        Args:
            text: Text to count tokens for

        Returns:
            Token count
        """
        if self.encoding is None:
            return len(text) // 4

        try:
            return len(self.encoding.encode(text))
        except Exception as e:
            logger.warning(f"Failed to encode text: {e}")
            return len(text) // 4

    def _fallback_count_messages(self, messages: List[Dict]) -> int:
        """Fallback to rough estimation if tiktoken unavailable.

        Args:
            messages: List of message dictionaries

        Returns:
            Estimated token count
        """
        total_chars = 0
        for msg in messages:
            try:
                total_chars += len(json.dumps(msg))
            except Exception:
                # If JSON serialization fails, count string representation
                total_chars += len(str(msg))

        # Use 4 chars per token (conservative estimate)
        return total_chars // 4


class AnthropicCounter:
    """Anthropic-specific token counter.

    Uses Anthropic's native token counting API when available.
    """

    def __init__(self, client=None):
        """Initialize with Anthropic client.

        Args:
            client: Anthropic client instance (optional)
        """
        self.client = client

    def count_messages(self, messages: List[Dict]) -> int:
        """Use Anthropic's native token counting.

        Args:
            messages: List of message dictionaries

        Returns:
            Token count
        """
        if self.client is None:
            return self._fallback_count(messages)

        try:
            # Anthropic client has count_tokens method
            count = self.client.count_tokens(messages)
            return count
        except AttributeError:
            logger.warning("Anthropic client doesn't have count_tokens method")
            return self._fallback_count(messages)
        except Exception as e:
            logger.warning(f"Anthropic token counting failed: {e}")
            return self._fallback_count(messages)

    def count_text(self, text: str) -> int:
        """Count tokens in text.

        Args:
            text: Text to count tokens for

        Returns:
            Token count
        """
        if self.client is None:
            return len(text) // 4

        try:
            return self.client.count_tokens([{"role": "user", "content": text}])
        except Exception:
            return len(text) // 4

    def _fallback_count(self, messages: List[Dict]) -> int:
        """Fallback to rough estimation.

        Args:
            messages: List of message dictionaries

        Returns:
            Estimated token count
        """
        total_chars = sum(len(json.dumps(msg)) for msg in messages)
        return total_chars // 4


class FallbackCounter:
    """Rough estimation fallback (chars / 4).

    Used when provider-specific counting is unavailable.
    Provides conservative estimates.
    """

    def count_messages(self, messages: List[Dict]) -> int:
        """Rough token estimation based on character count.

        Uses 4 characters per token as a conservative estimate.

        Args:
            messages: List of message dictionaries

        Returns:
            Estimated token count
        """
        total_chars = 0
        for msg in messages:
            try:
                total_chars += len(json.dumps(msg))
            except Exception:
                # If serialization fails, use string length
                total_chars += len(str(msg))

        # Use 4 chars per token (conservative)
        return max(1, total_chars // 4)

    def count_text(self, text: str) -> int:
        """Count tokens in text.

        Args:
            text: Text to count tokens for

        Returns:
            Estimated token count
        """
        return max(1, len(text) // 4)


def create_token_counter(
    provider: str,
    model: str,
    client: Optional[object] = None
) -> TokenCounter:
    """Factory function to create appropriate token counter.

    Args:
        provider: Provider name ("openai", "anthropic", etc.)
        model: Model name
        client: Optional provider client instance

    Returns:
        TokenCounter instance
    """
    provider_lower = provider.lower()

    if provider_lower in ("openai", "azure"):
        return TiktokenCounter(model=model)
    elif provider_lower == "anthropic":
        return AnthropicCounter(client=client)
    else:
        logger.info(f"Unknown provider '{provider}', using fallback counter")
        return FallbackCounter()
