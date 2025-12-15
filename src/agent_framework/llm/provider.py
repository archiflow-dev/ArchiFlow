"""
LLM Provider Abstraction.

Defines the interface for LLM providers and response types.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Iterator
from enum import Enum
import json
import logging

from .model_config import ModelRegistry, ModelConfig
from .usage_tracker import UsageTracker

logger = logging.getLogger(__name__)


class FinishReason(Enum):
    """Reasons why LLM generation finished."""
    STOP = "stop"
    TOOL_CALLS = "tool_calls"
    LENGTH = "length"
    ERROR = "error"


@dataclass
class ToolCallRequest:
    """Represents a tool call requested by the LLM."""
    id: str
    name: str
    arguments: str  # JSON string
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "arguments": self.arguments
        }


@dataclass
class LLMResponse:
    """Response from LLM generation."""
    content: Optional[str] = None
    tool_calls: List[ToolCallRequest] = field(default_factory=list)
    finish_reason: FinishReason = FinishReason.STOP
    usage: Dict[str, int] = field(default_factory=dict)
    
    @property
    def has_tool_calls(self) -> bool:
        """Check if response contains tool calls."""
        return len(self.tool_calls) > 0


@dataclass
class LLMResponseChunk:
    """Streaming response chunk from LLM."""
    content_delta: Optional[str] = None
    tool_call_delta: Optional[Dict[str, Any]] = None
    finish_reason: Optional[FinishReason] = None


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, model: str, usage_tracker: Optional[UsageTracker] = None, **kwargs):
        self.model = model
        self.config = kwargs
        self.model_config = ModelRegistry.get(model)
        self.usage_tracker = usage_tracker

        logger.info(
            f"Initialized {self.__class__.__name__} with model={model}, "
            f"context_window={self.model_config.context_window}, "
            f"usage_tracking={'enabled' if usage_tracker else 'disabled'}"
        )
    
    @abstractmethod
    def generate(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate a response from the LLM.
        
        Args:
            messages: List of messages in OpenAI format
            tools: Optional list of tool definitions
            **kwargs: Additional provider-specific arguments
        
        Returns:
            LLMResponse with content or tool calls
        """
        pass
    
    @abstractmethod
    def stream(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> Iterator[LLMResponseChunk]:
        """
        Stream responses from the LLM.

        Args:
            messages: List of messages in OpenAI format
            tools: Optional list of tool definitions
            **kwargs: Additional provider-specific arguments

        Yields:
            LLMResponseChunk objects
        """
        pass

    def count_tokens(self, messages: List[Dict[str, Any]]) -> int:
        """
        Count tokens in messages.

        Default implementation uses rough estimation (1 token ~= 4 chars).
        Providers should override with accurate counting (e.g., tiktoken for OpenAI).

        Args:
            messages: List of messages in OpenAI format

        Returns:
            Estimated token count
        """
        total_chars = 0
        for msg in messages:
            total_chars += len(json.dumps(msg))

        return total_chars // 4

    def count_tools_tokens(self, tools: Optional[List[Dict[str, Any]]]) -> int:
        """
        Count tokens used by tool definitions.

        Args:
            tools: List of tool definitions

        Returns:
            Estimated token count for tools
        """
        if not tools:
            return 0

        return len(json.dumps(tools)) // 4

    def _track_usage(self, response: LLMResponse, session_id: Optional[str] = None):
        """
        Track usage from an LLM response.

        Args:
            response: The LLM response containing usage info
            session_id: Optional session ID for tracking
        """
        if not self.usage_tracker:
            return

        usage = response.usage
        if not usage:
            return

        input_tokens = usage.get("prompt_tokens", usage.get("input_tokens", 0))
        output_tokens = usage.get("completion_tokens", usage.get("output_tokens", 0))

        if input_tokens > 0 or output_tokens > 0:
            self.usage_tracker.record(
                model_config=self.model_config,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                session_id=session_id
            )


class LLMFactory:
    """Factory for creating LLM providers."""
    
    _providers: Dict[str, type] = {}
    
    @classmethod
    def register(cls, name: str, provider_class: type):
        """Register a provider class."""
        cls._providers[name] = provider_class
    
    @classmethod
    def create(cls, provider_name: str, **config) -> LLMProvider:
        """Create an LLM provider instance."""
        if provider_name not in cls._providers:
            raise ValueError(f"Unknown provider: {provider_name}")
        
        provider_class = cls._providers[provider_name]
        return provider_class(**config)
