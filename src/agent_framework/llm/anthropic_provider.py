"""
Anthropic LLM Provider.

Provides integration with Anthropic's Claude models.
"""
import os
import logging
from typing import List, Dict, Any, Optional, Iterator
from .provider import LLMProvider, LLMResponse, LLMResponseChunk, FinishReason, ToolCallRequest
from ..config.env_loader import load_env

# Import anthropic
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

logger = logging.getLogger(__name__)

# Load environment variables
load_env()


class AnthropicProvider(LLMProvider):
    """Anthropic LLM Provider for Claude models."""

    def __init__(self, model: str = "claude-3-5-sonnet-20241022", api_key: Optional[str] = None, **kwargs):
        if not ANTHROPIC_AVAILABLE:
            raise ImportError(
                "anthropic package not installed. Install with: pip install anthropic"
            )

        # Extract usage_tracker before passing kwargs to parent
        usage_tracker = kwargs.pop('usage_tracker', None)

        super().__init__(model, usage_tracker=usage_tracker, **kwargs)

        # Override model from env if default is used
        if model == "claude-3-5-sonnet-20241022":
            self.model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")

        self.client = anthropic.Anthropic(
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"),
        )

        logger.info(f"Initialized AnthropicProvider with model {self.model}")

    def generate(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate a response from Anthropic."""

        # Convert OpenAI-style messages to Anthropic format
        anthropic_messages = self._convert_messages(messages)

        # Extract system message if present
        system = None
        if messages and messages[0].get("role") == "system":
            system = messages[0].get("content")
            anthropic_messages = anthropic_messages[1:]  # Remove system from messages

        # Prepare arguments
        create_kwargs = {
            "model": self.model,
            "messages": anthropic_messages,
            "max_tokens": kwargs.get("max_tokens", self.model_config.max_output_tokens),
        }

        if system:
            create_kwargs["system"] = system

        if tools:
            # Convert OpenAI-style tools to Anthropic format
            create_kwargs["tools"] = self._convert_tools(tools)

        # Add temperature if specified
        if "temperature" in kwargs:
            create_kwargs["temperature"] = kwargs["temperature"]

        try:
            response = self.client.messages.create(**create_kwargs)
        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            raise e

        # Parse response
        content = ""
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                content += block.text
            elif block.type == "tool_use":
                tool_calls.append(ToolCallRequest(
                    id=block.id,
                    name=block.name,
                    arguments=str(block.input) if isinstance(block.input, dict) else block.input
                ))

        # Map stop reason
        finish_reason_map = {
            "end_turn": FinishReason.STOP,
            "tool_use": FinishReason.TOOL_CALLS,
            "max_tokens": FinishReason.LENGTH,
        }

        llm_response = LLMResponse(
            content=content if content else None,
            tool_calls=tool_calls,
            finish_reason=finish_reason_map.get(response.stop_reason, FinishReason.STOP),
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            }
        )

        # Track usage
        self._track_usage(llm_response)

        return llm_response

    def stream(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> Iterator[LLMResponseChunk]:
        """Stream responses from Anthropic."""

        # Convert OpenAI-style messages to Anthropic format
        anthropic_messages = self._convert_messages(messages)

        # Extract system message if present
        system = None
        if messages and messages[0].get("role") == "system":
            system = messages[0].get("content")
            anthropic_messages = anthropic_messages[1:]

        create_kwargs = {
            "model": self.model,
            "messages": anthropic_messages,
            "max_tokens": kwargs.get("max_tokens", self.model_config.max_output_tokens),
            "stream": True
        }

        if system:
            create_kwargs["system"] = system

        if tools:
            create_kwargs["tools"] = self._convert_tools(tools)

        if "temperature" in kwargs:
            create_kwargs["temperature"] = kwargs["temperature"]

        stream = self.client.messages.create(**create_kwargs)

        for event in stream:
            if event.type == "content_block_delta":
                if hasattr(event.delta, "text"):
                    yield LLMResponseChunk(
                        content_delta=event.delta.text,
                        tool_call_delta=None,
                        finish_reason=None
                    )
                elif hasattr(event.delta, "partial_json"):
                    # Tool call in progress
                    yield LLMResponseChunk(
                        content_delta=None,
                        tool_call_delta={"partial_json": event.delta.partial_json},
                        finish_reason=None
                    )
            elif event.type == "message_stop":
                finish_reason_map = {
                    "end_turn": FinishReason.STOP,
                    "tool_use": FinishReason.TOOL_CALLS,
                    "max_tokens": FinishReason.LENGTH,
                }
                yield LLMResponseChunk(
                    content_delta=None,
                    tool_call_delta=None,
                    finish_reason=finish_reason_map.get(event.message.stop_reason, FinishReason.STOP)
                )

    def _convert_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert OpenAI-style messages to Anthropic format."""
        anthropic_messages = []

        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")

            # Skip system messages (handled separately)
            if role == "system":
                continue

            # Map assistant role
            if role == "assistant":
                anthropic_messages.append({
                    "role": "assistant",
                    "content": content or ""
                })
            elif role == "user":
                anthropic_messages.append({
                    "role": "user",
                    "content": content or ""
                })

        return anthropic_messages

    def _convert_tools(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert OpenAI-style tools to Anthropic format."""
        anthropic_tools = []

        for tool in tools:
            if tool.get("type") == "function":
                func = tool.get("function", {})
                anthropic_tools.append({
                    "name": func.get("name"),
                    "description": func.get("description"),
                    "input_schema": func.get("parameters", {})
                })

        return anthropic_tools

    def count_tokens(self, messages: List[Dict[str, Any]]) -> int:
        """
        Count tokens using Anthropic's client.

        Note: Anthropic provides token counting via their API.
        For now, using rough estimation similar to parent class.
        """
        # Use rough estimation (1 token ~= 4 chars)
        return super().count_tokens(messages)
