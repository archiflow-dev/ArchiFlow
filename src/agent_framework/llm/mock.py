"""
Mock LLM Provider for testing.
"""
from typing import List, Dict, Any, Optional, Iterator
import json
from .provider import (
    LLMProvider, LLMResponse, LLMResponseChunk,
    FinishReason, ToolCallRequest, LLMFactory
)


class MockProvider(LLMProvider):
    """Mock LLM provider for testing."""
    
    def __init__(self, model: str = "mock-model", **kwargs):
        super().__init__(model, **kwargs)
        self.responses: List[LLMResponse] = []
        self.call_count = 0
    
    def set_response(self, response: LLMResponse):
        """Set the next response to return."""
        self.responses = [response]
    
    def set_responses(self, responses: List[LLMResponse]):
        """Set a list of responses to return in sequence."""
        self.responses = responses
    
    def generate(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> LLMResponse:
        """Return mock response."""
        self.call_count += 1
        
        if self.responses:
            response = self.responses.pop(0)
            return response
        
        # Default response
        return LLMResponse(
            content="This is a mock response",
            finish_reason=FinishReason.STOP,
            usage={"total_tokens": 10}
        )
    
    def stream(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> Iterator[LLMResponseChunk]:
        """Yield mock chunks."""
        chunks = ["This ", "is ", "a ", "mock ", "stream"]
        
        for chunk in chunks:
            yield LLMResponseChunk(content_delta=chunk)
        
        yield LLMResponseChunk(finish_reason=FinishReason.STOP)
    
    def reset(self):
        """Reset mock state."""
        self.responses = []
        self.call_count = 0


# Convenience alias
MockLLMProvider = MockProvider

# Register mock provider
LLMFactory.register("mock", MockProvider)
