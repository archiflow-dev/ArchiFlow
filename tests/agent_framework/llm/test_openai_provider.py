import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../src')))

from agent_framework.llm.openai_provider import OpenAIProvider
from agent_framework.llm.provider import FinishReason

class TestOpenAIProvider(unittest.TestCase):
    def setUp(self):
        self.api_key = "test_key"
        self.model = "gpt-4"
        
    @patch("agent_framework.llm.openai_provider.OpenAI")
    def test_initialization(self, mock_openai):
        provider = OpenAIProvider(model=self.model, api_key=self.api_key)
        
        mock_openai.assert_called_with(
            api_key=self.api_key,
            base_url=None
        )
        self.assertEqual(provider.model, self.model)

    @patch("agent_framework.llm.openai_provider.OpenAI")
    def test_generate(self, mock_openai):
        # Setup mock response
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        
        mock_message.content = "Test response"
        mock_message.tool_calls = None
        mock_choice.message = mock_message
        mock_choice.finish_reason = "stop"
        mock_response.choices = [mock_choice]
        mock_response.usage = None
        
        mock_client.chat.completions.create.return_value = mock_response
        
        provider = OpenAIProvider(model=self.model, api_key=self.api_key)
        messages = [{"role": "user", "content": "Hello"}]
        
        response = provider.generate(messages)
        
        # Verify call
        mock_client.chat.completions.create.assert_called_with(
            model=self.model,
            messages=messages
        )
        
        # Verify result
        self.assertEqual(response.content, "Test response")
        self.assertEqual(response.finish_reason, FinishReason.STOP)

    @patch("agent_framework.llm.openai_provider.OpenAI")
    def test_stream(self, mock_openai):
        # Setup mock stream
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        # Create mock chunks
        chunk1 = MagicMock()
        chunk1.choices = [MagicMock(delta=MagicMock(content="Hello", tool_calls=None), finish_reason=None)]
        
        chunk2 = MagicMock()
        chunk2.choices = [MagicMock(delta=MagicMock(content=" World", tool_calls=None), finish_reason="stop")]
        
        mock_client.chat.completions.create.return_value = iter([chunk1, chunk2])
        
        provider = OpenAIProvider(model=self.model, api_key=self.api_key)
        messages = [{"role": "user", "content": "Hello"}]
        
        chunks = list(provider.stream(messages))
        
        # Verify call
        mock_client.chat.completions.create.assert_called_with(
            model=self.model,
            messages=messages,
            stream=True
        )
        
        # Verify result
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0].content_delta, "Hello")
        self.assertEqual(chunks[1].content_delta, " World")

if __name__ == '__main__':
    unittest.main()
