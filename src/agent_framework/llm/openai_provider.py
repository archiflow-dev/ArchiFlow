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

class OpenAIProvider(LLMProvider):
    """OpenAI LLM Provider with accurate token counting."""

    def __init__(self, model: str = "gpt-5", api_key: Optional[str] = None, base_url: Optional[str] = None, **kwargs):
        # Extract usage_tracker before passing kwargs to parent and OpenAI
        usage_tracker = kwargs.pop('usage_tracker', None)

        super().__init__(model, usage_tracker=usage_tracker, **kwargs)

        # Override model from env if default is used
        if model == "gpt-5":
             self.model = os.getenv("OPENAI_MODEL", "gpt-5")

        self.client = OpenAI(
            api_key=api_key or os.environ.get("OPENAI_API_KEY"),
            base_url=base_url,
            **kwargs
        )

        # Initialize tiktoken encoding if available
        self.encoding = None
        if TIKTOKEN_AVAILABLE:
            try:
                self.encoding = tiktoken.encoding_for_model(self.model)
                logger.info(f"Using tiktoken for accurate token counting ({self.model})")
            except KeyError:
                # Fallback to cl100k_base for unknown models
                self.encoding = tiktoken.get_encoding("cl100k_base")
                logger.info(f"Unknown model for tiktoken, using cl100k_base encoding")
        else:
            logger.warning(
                "tiktoken not installed, using rough token estimation. "
                "Install with: pip install tiktoken"
            )

    def generate(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate a response from OpenAI."""
        
        # Prepare arguments
        create_kwargs = {
            "model": self.model,
            "messages": messages,
        }
        if tools:
            create_kwargs["tools"] = tools
            create_kwargs["tool_choice"] = kwargs.get("tool_choice", "auto")
            
        # Add any other kwargs
        create_kwargs.update(kwargs)
        
        # Remove provider-specific args if they shouldn't be passed to create
        # (none for now, assuming kwargs are clean)
        try:
            response = self.client.chat.completions.create(**create_kwargs)
        except Exception as e:
            print(f"LLM complete error: {e} \n kwargs: {create_kwargs}")
            raise e


        choice = response.choices[0]
        message = choice.message
        
        tool_calls = []
        if message.tool_calls:
            for tc in message.tool_calls:
                tool_calls.append(ToolCallRequest(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=tc.function.arguments
                ))
        
        finish_reason_map = {
            "stop": FinishReason.STOP,
            "tool_calls": FinishReason.TOOL_CALLS,
            "length": FinishReason.LENGTH,
            "content_filter": FinishReason.ERROR, # Mapping content_filter to error for now or add new enum
        }
        
        llm_response = LLMResponse(
            content=message.content,
            tool_calls=tool_calls,
            finish_reason=finish_reason_map.get(choice.finish_reason, FinishReason.STOP),
            usage=response.usage.model_dump() if response.usage else {}
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
        """Stream responses from OpenAI."""
        
        create_kwargs = {
            "model": self.model,
            "messages": messages,
            "stream": True
        }
        if tools:
            create_kwargs["tools"] = tools
            create_kwargs["tool_choice"] = kwargs.get("tool_choice", "auto")
            
        create_kwargs.update(kwargs)
        
        stream = self.client.chat.completions.create(**create_kwargs)
        
        for chunk in stream:
            choice = chunk.choices[0]
            delta = choice.delta
            
            tool_call_delta = None
            if delta.tool_calls:
                # OpenAI sends list of tool calls in delta, usually one at a time or partial
                # For simplicity in this abstraction, we might need to handle this carefully.
                # Here we just pass the raw dict for the consumer to aggregate.
                tool_call_delta = {
                    "index": delta.tool_calls[0].index,
                    "id": delta.tool_calls[0].id,
                    "function": {
                        "name": delta.tool_calls[0].function.name,
                        "arguments": delta.tool_calls[0].function.arguments
                    }
                }

            finish_reason = None
            if choice.finish_reason:
                 finish_reason_map = {
                    "stop": FinishReason.STOP,
                    "tool_calls": FinishReason.TOOL_CALLS,
                    "length": FinishReason.LENGTH,
                }
                 finish_reason = finish_reason_map.get(choice.finish_reason)

            yield LLMResponseChunk(
                content_delta=delta.content,
                tool_call_delta=tool_call_delta,
                finish_reason=finish_reason
            )

    def count_tokens(self, messages: List[Dict[str, Any]]) -> int:
        """
        Count tokens in messages using tiktoken (if available).

        Based on OpenAI's token counting guide:
        https://github.com/openai/openai-cookbook/blob/main/examples/How_to_count_tokens_with_tiktoken.ipynb

        Args:
            messages: List of messages in OpenAI format

        Returns:
            Accurate token count (if tiktoken available), otherwise rough estimate
        """
        if not self.encoding:
            # Fallback to parent class rough estimation
            return super().count_tokens(messages)

        num_tokens = 0

        # Message overhead (varies by model)
        tokens_per_message = 3  # gpt-4, gpt-3.5-turbo
        tokens_per_name = 1

        for message in messages:
            num_tokens += tokens_per_message

            for key, value in message.items():
                if value is None:
                    continue

                # Encode the value
                if isinstance(value, str):
                    num_tokens += len(self.encoding.encode(value))
                elif isinstance(value, list):
                    # Handle tool_calls or other lists
                    import json
                    num_tokens += len(self.encoding.encode(json.dumps(value)))
                elif isinstance(value, dict):
                    import json
                    num_tokens += len(self.encoding.encode(json.dumps(value)))
                else:
                    num_tokens += len(self.encoding.encode(str(value)))

                if key == "name":
                    num_tokens += tokens_per_name

        num_tokens += 3  # Every reply is primed with assistant
        return num_tokens

    def count_tools_tokens(self, tools: Optional[List[Dict[str, Any]]]) -> int:
        """
        Count tokens used by tool definitions.

        Args:
            tools: List of tool definitions

        Returns:
            Accurate token count (if tiktoken available), otherwise rough estimate
        """
        if not tools:
            return 0

        if not self.encoding:
            return super().count_tools_tokens(tools)

        import json
        tools_str = json.dumps(tools)
        return len(self.encoding.encode(tools_str))
