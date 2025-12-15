"""
Tests for GLM LLM Provider.

Note: These tests require a ZHIPU_API_KEY environment variable
to run actual API tests. Without it, tests will use mock mode.
"""
import pytest
import os
from unittest.mock import Mock, patch, MagicMock
from agent_framework.llm.glm_provider import GLMProvider
from agent_framework.llm.provider import LLMResponse, ToolCallRequest, FinishReason


# Skip tests if no API key
SKIP_REASON = "ZHIPU_API_KEY environment variable not set"
skip_if_no_key = pytest.mark.skipif(
    not os.getenv("ZHIPU_API_KEY"),
    reason=SKIP_REASON
)


class TestGLMProviderInit:
    """Test GLM provider initialization."""

    def test_init_with_default_values(self):
        """Test initialization with default values."""
        provider = GLMProvider()

        assert provider.model == "glm-4"
        assert str(provider.client.base_url).rstrip('/') == "https://api.z.ai/api/paas/v4"

    def test_init_with_custom_values(self):
        """Test initialization with custom values."""
        provider = GLMProvider(
            model="glm-4-plus",
            api_key="test-key",
            base_url="https://custom.url"
        )

        assert provider.model == "glm-4-plus"
        assert provider.client.api_key == "test-key"
        assert provider.client.base_url == "https://custom.url"

    @patch.dict(os.environ, {"ZHIPU_API_KEY": "env-key"})
    def test_init_with_env_key(self):
        """Test initialization with API key from environment."""
        provider = GLMProvider()
        assert provider.client.api_key == "env-key"


class TestGLMProviderResponseParsing:
    """Test response parsing logic without actual API calls."""

    def test_parse_text_response(self):
        """Test parsing a simple text response."""
        provider = GLMProvider(api_key="test")

        # Mock OpenAI response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = "Hello, world!"
        mock_response.choices[0].message.tool_calls = None
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15

        # Mock the API client
        provider.client.chat.completions.create = Mock(return_value=mock_response)

        response = provider.generate([{"role": "user", "content": "Hi"}])

        assert response.content == "Hello, world!"
        assert response.finish_reason == FinishReason.STOP
        assert len(response.tool_calls) == 0
        assert response.usage["prompt_tokens"] == 10
        assert response.usage["completion_tokens"] == 5
        assert response.usage["total_tokens"] == 15

    def test_parse_tool_call_response(self):
        """Test parsing a response with tool calls."""
        provider = GLMProvider(api_key="test")

        # Mock tool call
        mock_tool = Mock()
        mock_tool.id = "call_123"
        mock_tool.function.name = "test_tool"
        mock_tool.function.arguments = '{"arg": "value"}'

        # Mock OpenAI response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = None
        mock_response.choices[0].message.tool_calls = [mock_tool]
        mock_response.choices[0].finish_reason = "tool_calls"
        mock_response.usage = None

        # Mock the API client
        provider.client.chat.completions.create = Mock(return_value=mock_response)

        response = provider.generate(
            [{"role": "user", "content": "Use tool"}],
            tools=[{"name": "test_tool", "description": "Test"}]
        )

        assert response.content is None
        assert response.finish_reason == FinishReason.TOOL_CALLS
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].id == "call_123"
        assert response.tool_calls[0].name == "test_tool"
        assert response.tool_calls[0].arguments == '{"arg": "value"}'

    def test_stream_response_parsing(self):
        """Test parsing streaming responses."""
        provider = GLMProvider(api_key="test")

        # Create mock stream chunks
        chunks = [
            # First chunk with content
            Mock(choices=[Mock(finish_reason=None, delta=Mock(content="Hello", tool_calls=[]))]),
            # Second chunk with content
            Mock(choices=[Mock(finish_reason=None, delta=Mock(content=" world", tool_calls=[]))]),
            # Final chunk
            Mock(choices=[Mock(finish_reason="stop", delta=Mock(content="", tool_calls=[]))]),
        ]

        # Mock the streaming client to return an iterator
        provider.client.chat.completions.create = Mock(return_value=iter(chunks))

        stream = provider.stream([{"role": "user", "content": "Hi"}])

        collected_content = ""
        for chunk in stream:
            if chunk.content_delta:
                collected_content += chunk.content_delta
            if chunk.finish_reason:
                assert chunk.finish_reason == FinishReason.STOP

        assert collected_content == "Hello world"

    def test_finish_reason_mapping(self):
        """Test mapping GLM finish reasons to our enum."""
        provider = GLMProvider(api_key="test")

        finish_reason_map = {
            "stop": FinishReason.STOP,
            "tool_calls": FinishReason.TOOL_CALLS,
            "length": FinishReason.LENGTH,
            "content_filter": FinishReason.ERROR,
            "error": FinishReason.ERROR,
            "unknown": FinishReason.ERROR,  # Default
        }

        for glm_reason, expected in finish_reason_map.items():
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].finish_reason = glm_reason
            mock_response.choices[0].message = Mock()
            mock_response.choices[0].message.content = "test"
            mock_response.choices[0].message.tool_calls = None
            mock_response.usage = None

            provider.client.chat.completions.create = Mock(return_value=mock_response)
            response = provider.generate([{"role": "user", "content": "test"}])

            assert response.finish_reason == expected

    def test_model_info(self):
        """Test getting model information."""
        provider = GLMProvider(api_key="test", model="glm-4-plus")
        info = provider.get_model_info()

        assert info["provider"] == "zhipu"
        assert info["model"] == "glm-4-plus"
        assert info["supports_tools"] is True
        assert info["supports_streaming"] is True
        assert info["api_format"] == "openai-compatible"
        assert info["context_window"] == 128000


class TestGLMProviderTokenCounting:
    """Test token counting functionality."""

    @patch('agent_framework.llm.glm_provider.TIKTOKEN_AVAILABLE', False)
    def test_token_counting_without_tiktoken(self):
        """Test token counting when tiktoken is not available."""
        provider = GLMProvider(api_key="test")

        messages = [
            {"role": "user", "content": "Hello, world!"},
            {"role": "assistant", "content": "Hi there!"}
        ]

        count = provider.count_tokens(messages)
        # Should use rough estimation (1 token ~= 4 chars)
        assert count > 0
        assert isinstance(count, int)

    @patch('agent_framework.llm.glm_provider.TIKTOKEN_AVAILABLE', True)
    @patch('agent_framework.llm.glm_provider.tiktoken')
    def test_token_counting_with_tiktoken(self, mock_tiktoken):
        """Test token counting with tiktoken."""
        # Mock tiktoken encoding
        mock_encoding = Mock()
        mock_encoding.encode = Mock(return_value=[1, 2, 3, 4, 5])  # 5 tokens
        mock_tiktoken.get_encoding.return_value = mock_encoding

        provider = GLMProvider(api_key="test")

        messages = [
            {"role": "user", "content": "Hello"}
        ]

        count = provider.count_tokens(messages)
        assert count == 5
        mock_encoding.encode.assert_called()

    def test_tools_token_counting(self):
        """Test counting tokens for tool definitions."""
        provider = GLMProvider(api_key="test")

        tools = [
            {
                "name": "test_tool",
                "description": "A test tool",
                "parameters": {"type": "object", "properties": {}}
            }
        ]

        count = provider.count_tools_tokens(tools)
        # Should return estimated token count
        assert count > 0
        assert isinstance(count, int)

    def test_tools_token_counting_empty(self):
        """Test counting tokens when no tools are provided."""
        provider = GLMProvider(api_key="test")

        count = provider.count_tools_tokens(None)
        assert count == 0

        count = provider.count_tools_tokens([])
        assert count == 0


@skip_if_no_key
class TestGLMProviderIntegration:
    """Integration tests that require actual API calls."""

    def test_generate_simple_text(self):
        """Test generating simple text."""
        provider = GLMProvider(
            model="glm-4-flash",  # Use cheaper model for testing
            api_key=os.getenv("ZHIPU_API_KEY")
        )

        response = provider.generate([
            {"role": "user", "content": "Say 'Hello GLM' in one sentence."}
        ])

        assert response.content is not None
        assert "Hello GLM" in response.content
        assert response.finish_reason == FinishReason.STOP

    def test_generate_with_tools(self):
        """Test generating with tool definitions."""
        provider = GLMProvider(
            model="glm-4-flash",
            api_key=os.getenv("ZHIPU_API_KEY")
        )

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get current weather",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "City name"
                            }
                        },
                        "required": ["location"]
                    }
                }
            }
        ]

        response = provider.generate(
            [{"role": "user", "content": "What's the weather in Beijing?"}],
            tools=tools
        )

        # GLM might call the tool or provide text response
        assert response.content is not None or len(response.tool_calls) > 0

    def test_stream_generate(self):
        """Test streaming generation."""
        provider = GLMProvider(
            model="glm-4-flash",
            api_key=os.getenv("ZHIPU_API_KEY")
        )

        chunks = list(provider.stream([
            {"role": "user", "content": "Count from 1 to 5"}
        ]))

        # Should receive multiple chunks
        assert len(chunks) > 0

        # Collect content from chunks
        content = ""
        for chunk in chunks:
            if chunk.content_delta:
                content += chunk.content_delta

        # Should have received some content
        assert len(content) > 0

    def test_context_limits(self):
        """Test handling of context limits."""
        provider = GLMProvider(
            model="glm-4",
            api_key=os.getenv("ZHIPU_API_KEY")
        )

        # Test with a long message (but not exceeding context)
        long_text = "This is a test. " * 100  # ~1300 tokens

        response = provider.generate([
            {"role": "user", "content": long_text}
        ])

        assert response.content is not None
        assert len(response.content) > 0


def test_provider_registration():
    """Test that the GLM provider is properly registered."""
    from agent_framework.llm.provider import LLMFactory

    # Check if GLM provider is registered
    assert "glm" in LLMFactory._providers
    assert LLMFactory._providers["glm"] == GLMProvider


if __name__ == "__main__":
    # Run a simple test if called directly
    import sys

    print("GLM Provider Tests")
    print("-" * 40)

    if not os.getenv("ZHIPU_API_KEY"):
        print(f"SKIP: {SKIP_REASON}")
        sys.exit(0)

    # Run basic integration test
    try:
        provider = GLMProvider(api_key=os.getenv("ZHIPU_API_KEY"))
        response = provider.generate([
            {"role": "user", "content": "Say 'GLM provider works!'"}
        ])
        print(f"✓ Response: {response.content[:50]}...")
    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)