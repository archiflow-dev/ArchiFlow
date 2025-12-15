"""Tests for LLM providers."""
import unittest
from src.agent_framework.llm.provider import (
    LLMProvider, LLMResponse, LLMResponseChunk,
    FinishReason, ToolCallRequest, LLMFactory
)
from src.agent_framework.llm.mock import MockProvider


class TestLLMResponse(unittest.TestCase):
    """Test LLMResponse dataclass."""
    
    def test_simple_response(self):
        """Test basic response."""
        response = LLMResponse(content="Hello")
        self.assertEqual(response.content, "Hello")
        self.assertFalse(response.has_tool_calls)
    
    def test_tool_call_response(self):
        """Test response with tool calls."""
        tool_call = ToolCallRequest(
            id="call_1",
            name="read_file",
            arguments='{"path": "/test.txt"}'
        )
        response = LLMResponse(tool_calls=[tool_call])
        self.assertTrue(response.has_tool_calls)
        self.assertEqual(len(response.tool_calls), 1)


class TestMockProvider(unittest.TestCase):
    """Test MockProvider."""
    
    def setUp(self):
        self.provider = MockProvider()
    
    def test_default_response(self):
        """Test default mock response."""
        response = self.provider.generate([{"role": "user", "content": "Hi"}])
        
        self.assertIsNotNone(response.content)
        self.assertEqual(response.finish_reason, FinishReason.STOP)
        self.assertEqual(self.provider.call_count, 1)
    
    def test_set_custom_response(self):
        """Test setting custom response."""
        custom_response = LLMResponse(
            content="Custom answer",
            finish_reason=FinishReason.STOP
        )
        self.provider.set_response(custom_response)
        
        response = self.provider.generate([])
        self.assertEqual(response.content, "Custom answer")
    
    def test_multiple_responses(self):
        """Test multiple sequential responses."""
        responses = [
            LLMResponse(content="First"),
            LLMResponse(content="Second"),
            LLMResponse(content="Third")
        ]
        self.provider.set_responses(responses)
        
        r1 = self.provider.generate([])
        r2 = self.provider.generate([])
        r3 = self.provider.generate([])
        
        self.assertEqual(r1.content, "First")
        self.assertEqual(r2.content, "Second")
        self.assertEqual(r3.content, "Third")
    
    def test_stream(self):
        """Test streaming."""
        chunks = list(self.provider.stream([]))
        
        self.assertGreater(len(chunks), 0)
        # Last chunk should have finish reason
        self.assertIsNotNone(chunks[-1].finish_reason)
    
    def test_reset(self):
        """Test resetting mock."""
        self.provider.generate([])
        self.assertEqual(self.provider.call_count, 1)
        
        self.provider.reset()
        self.assertEqual(self.provider.call_count, 0)


class TestLLMFactory(unittest.TestCase):
    """Test LLMFactory."""
    
    def test_create_mock_provider(self):
        """Test creating mock provider via factory."""
        provider = LLMFactory.create("mock", model="test-model")
        
        self.assertIsInstance(provider, MockProvider)
        self.assertEqual(provider.model, "test-model")
    
    def test_unknown_provider(self):
        """Test error with unknown provider."""
        with self.assertRaises(ValueError):
            LLMFactory.create("nonexistent")


if __name__ == '__main__':
    unittest.main()
