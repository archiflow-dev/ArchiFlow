"""
GLM LLM Provider for Zhipu AI's GLM models.

This provider supports GLM-4.6, GLM-4, GLM-4-Plus, and GLM-4-Air models
using the OpenAI-compatible API format.
"""
import os
import logging
from typing import List, Dict, Any, Optional, Iterator
from openai import OpenAI
from .provider import LLMProvider, LLMResponse, LLMResponseChunk, FinishReason, ToolCallRequest
from ..config.env_loader import load_env

# Optional: tiktoken for accurate token counting
try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False

logger = logging.getLogger(__name__)

# Load environment variables
load_env()


class GLMProvider(LLMProvider):
    """GLM LLM Provider for Zhipu AI models."""

    def __init__(
        self,
        model: str = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize GLM Provider.

        Args:
            model: GLM model name (default: "glm-4")
            api_key: Zhipu AI API key (from env if not provided)
            base_url: Custom base URL (uses Zhipu's if not provided)
            **kwargs: Additional arguments passed to OpenAI client
        """
        # Extract usage_tracker before passing kwargs to parent and OpenAI
        usage_tracker = kwargs.pop('usage_tracker', None)

        # Get model from environment if not provided
        if model is None:
            model = os.getenv("ZAI_MODEL", "glm-4.6")

        super().__init__(model, usage_tracker=usage_tracker, **kwargs)

        # Use Zhipu's international OpenAI-compatible endpoint by default
        # z.ai is the international version of bigmodel.cn
        if base_url is None:
            # base_url = "https://api.z.ai/api/paas/v4/"
            base_url = "https://api.z.ai/api/coding/paas/v4"

        # Check for API key from multiple sources
        api_key = api_key or os.environ.get("ZAI_API_KEY") or os.environ.get("ZHIPU_API_KEY")

        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            **kwargs
        )

        # Initialize tiktoken encoding if available
        # GLM-4 uses a tokenizer similar to GPT-4
        self.encoding = None
        if TIKTOKEN_AVAILABLE:
            try:
                # Try to get encoding for GLM models
                # GLM-4 seems to use a tokenizer similar to cl100k_base
                self.encoding = tiktoken.get_encoding("cl100k_base")
                logger.info(f"Using tiktoken cl100k_base encoding for GLM model: {model}")
            except Exception as e:
                logger.warning(f"Failed to initialize tiktoken: {e}")
                logger.info(
                    "Using rough token estimation. "
                    "Install tiktoken for better accuracy: pip install tiktoken"
                )
        else:
            logger.info(
                "tiktoken not installed, using rough token estimation. "
                "Install with: pip install tiktoken"
            )

        # Map GLM models to context windows
        self.model_context_windows = {
            "glm-4": 128000,
            "glm-4-plus": 128000,
            "glm-4-air": 128000,
            "glm-4-airx": 128000,
            "glm-4-long": 128000,
            "glm-4-flash": 128000,
            "glm-3-turbo": 128000,
        }

    def generate(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate a response from GLM.

        Args:
            messages: List of messages in OpenAI format
            tools: Optional list of tool definitions
            **kwargs: Additional generation parameters

        Returns:
            LLMResponse with content or tool calls
        """
        # Prepare arguments
        create_kwargs = {
            "model": self.model,
            "messages": messages,
        }

        # Add tools if provided
        if tools:
            create_kwargs["tools"] = tools
            create_kwargs["tool_choice"] = kwargs.get("tool_choice", "auto")

        # Add any other kwargs
        create_kwargs.update(kwargs)

        # Remove provider-specific args that shouldn't be passed to create
        # (none for now, assuming kwargs are clean)

        try:
            response = self.client.chat.completions.create(**create_kwargs)
        except Exception as e:
            logger.error(f"GLM API error: {e}")
            logger.error(f"Request kwargs: {create_kwargs}")
            raise

        choice = response.choices[0]
        message = choice.message

        # Extract tool calls
        tool_calls = []
        if message.tool_calls:
            for tc in message.tool_calls:
                tool_calls.append(ToolCallRequest(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=tc.function.arguments
                ))

        # Map GLM finish reasons to our enum
        finish_reason_map = {
            "stop": FinishReason.STOP,
            "tool_calls": FinishReason.TOOL_CALLS,
            "length": FinishReason.LENGTH,
            "content_filter": FinishReason.ERROR,
            "error": FinishReason.ERROR,
        }

        finish_reason = finish_reason_map.get(
            choice.finish_reason,
            FinishReason.ERROR
        )

        # Extract usage information
        usage = {}
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        # Track usage
        llm_response = LLMResponse(
            content=message.content,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage=usage
        )
        self._track_usage(llm_response, kwargs.get("session_id"))

        return llm_response

    def stream(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> Iterator[LLMResponseChunk]:
        """
        Stream responses from GLM.

        Args:
            messages: List of messages in OpenAI format
            tools: Optional list of tool definitions
            **kwargs: Additional generation parameters

        Yields:
            LLMResponseChunk objects
        """
        # Prepare arguments
        create_kwargs = {
            "model": self.model,
            "messages": messages,
            "stream": True,
        }

        if tools:
            create_kwargs["tools"] = tools
            create_kwargs["tool_choice"] = kwargs.get("tool_choice", "auto")

        # Add any other kwargs
        create_kwargs.update(kwargs)

        try:
            stream_response = self.client.chat.completions.create(**create_kwargs)
        except Exception as e:
            logger.error(f"GLM stream error: {e}")
            raise

        # The create method with stream=True returns an iterator directly
        for chunk in stream_response:
            choice = chunk.choices[0]
            delta = choice.delta

            # Map finish reasons
            finish_reason = None
            if choice.finish_reason is not None:
                finish_reason_map = {
                    "stop": FinishReason.STOP,
                    "tool_calls": FinishReason.TOOL_CALLS,
                    "length": FinishReason.LENGTH,
                    "content_filter": FinishReason.ERROR,
                    "error": FinishReason.ERROR,
                }
                finish_reason = finish_reason_map.get(choice.finish_reason)

            # Handle tool call deltas
            tool_call_delta = None
            if delta.tool_calls:
                tool_call_delta = {}
                for tc in delta.tool_calls:
                    tool_call_delta[tc.index] = {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name if tc.function else None,
                            "arguments": tc.function.arguments if tc.function else None,
                        }
                    }

            yield LLMResponseChunk(
                content_delta=delta.content,
                tool_call_delta=tool_call_delta,
                finish_reason=finish_reason
            )

    def count_tokens(self, messages: List[Dict[str, Any]]) -> int:
        """
        Count tokens in messages using tiktoken if available.

        Args:
            messages: List of messages in OpenAI format

        Returns:
            Token count
        """
        if self.encoding:
            # Use tiktoken for accurate counting
            total_tokens = 0
            for message in messages:
                # Count role and content
                total_tokens += len(
                    self.encoding.encode(
                        message.get("role", "") + message.get("content", "")
                    )
                )
                # Count tool calls if present
                if "tool_calls" in message:
                    for tc in message["tool_calls"]:
                        if "function" in tc:
                            func = tc["function"]
                            total_tokens += len(
                                self.encoding.encode(
                                    func.get("name", "") + func.get("arguments", "")
                                )
                            )
            return total_tokens
        else:
            # Fallback to parent's rough estimation
            return super().count_tokens(messages)

    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the current model.

        Returns:
            Dictionary with model information
        """
        return {
            "provider": "zhipu",
            "model": self.model,
            "context_window": self.model_context_windows.get(
                self.model,
                self.model_config.context_window
            ),
            "supports_tools": True,
            "supports_streaming": True,
            "api_format": "openai-compatible",
        }


# Register the provider
from .provider import LLMFactory
LLMFactory.register("glm", GLMProvider)