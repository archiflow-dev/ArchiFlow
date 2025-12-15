"""Tests for ConversationHistory."""
import unittest
from src.agent_framework.agents.history import ConversationHistory
from src.agent_framework.messages.types import (
    UserMessage, SystemMessage, LLMThinkMessage, LLMRespondMessage,
    ToolCallMessage, ToolCall, ToolResultObservation, ErrorObservation,
    EnvironmentMessage
)


class TestConversationHistory(unittest.TestCase):
    """Test ConversationHistory basic operations."""
    
    def setUp(self):
        self.history = ConversationHistory()
    
    def test_add_message(self):
        """Test adding messages to history."""
        msg1 = UserMessage(session_id="test", sequence=1, content="Hello")
        msg2 = SystemMessage(session_id="test", sequence=2, content="Hi")
        
        self.history.add(msg1)
        self.history.add(msg2)
        
        self.assertEqual(len(self.history), 2)
        self.assertEqual(self.history.messages[0].content, "Hello")
        self.assertEqual(self.history.messages[1].content, "Hi")
    
    def test_get_recent(self):
        """Test getting recent messages."""
        for i in range(10):
            msg = UserMessage(session_id="test", sequence=i, content=f"Msg {i}")
            self.history.add(msg)
        
        recent = self.history.get_recent(3)
        self.assertEqual(len(recent), 3)
        self.assertEqual(recent[0].content, "Msg 7")
        self.assertEqual(recent[2].content, "Msg 9")
    
    def test_get_recent_more_than_available(self):
        """Test getting recent when requesting more than available."""
        msg = UserMessage(session_id="test", sequence=1, content="Only one")
        self.history.add(msg)
        
        recent = self.history.get_recent(10)
        self.assertEqual(len(recent), 1)
    
    def test_get_recent_zero(self):
        """Test getting zero recent messages."""
        self.history.add(UserMessage(session_id="test", sequence=1, content="Test"))
        recent = self.history.get_recent(0)
        self.assertEqual(len(recent), 0)
    
    def test_clear(self):
        """Test clearing history."""
        self.history.add(UserMessage(session_id="test", sequence=1, content="Test"))
        self.history.add(UserMessage(session_id="test", sequence=2, content="Test2"))
        self.assertEqual(len(self.history), 2)
        
        self.history.clear()
        self.assertEqual(len(self.history), 0)


class TestLLMFormatConversion(unittest.TestCase):
    """Test conversion to LLM API format."""
    
    def setUp(self):
        self.history = ConversationHistory()
    
    def test_user_message_conversion(self):
        """Test UserMessage converts to user role."""
        msg = UserMessage(session_id="test", sequence=1, content="Hello, AI")
        self.history.add(msg)
        
        llm_format = self.history.to_llm_format()
        self.assertEqual(len(llm_format), 1)
        self.assertEqual(llm_format[0]["role"], "user")
        self.assertEqual(llm_format[0]["content"], "Hello, AI")
    
    def test_system_message_conversion(self):
        """Test SystemMessage converts to system role."""
        msg = SystemMessage(session_id="test", sequence=1, content="You are a helpful assistant")
        self.history.add(msg)
        
        llm_format = self.history.to_llm_format()
        self.assertEqual(llm_format[0]["role"], "system")
        self.assertEqual(llm_format[0]["content"], "You are a helpful assistant")
    
    def test_llm_messages_conversion(self):
        """Test LLM messages convert to assistant role."""
        think = LLMThinkMessage(session_id="test", sequence=1, content="Let me think...")
        respond = LLMRespondMessage(session_id="test", sequence=2, content="Here's the answer")
        
        self.history.add(think)
        self.history.add(respond)
        
        llm_format = self.history.to_llm_format()
        self.assertEqual(len(llm_format), 2)
        self.assertEqual(llm_format[0]["role"], "assistant")
        self.assertEqual(llm_format[0]["content"], "Let me think...")
        self.assertEqual(llm_format[1]["role"], "assistant")
        self.assertEqual(llm_format[1]["content"], "Here's the answer")
    
    def test_tool_call_conversion(self):
        """Test ToolCallMessage converts to assistant with tool_calls."""
        tool_call = ToolCall(
            id="call_123",
            tool_name="read_file",
            arguments={"path": "/test.txt"}
        )
        msg = ToolCallMessage(session_id="test", sequence=1, tool_calls=[tool_call])
        self.history.add(msg)
        
        llm_format = self.history.to_llm_format()
        self.assertEqual(llm_format[0]["role"], "assistant")
        self.assertEqual(llm_format[0]["content"], "")  # Changed: content must be empty string, not None
        self.assertIn("tool_calls", llm_format[0])
        self.assertEqual(len(llm_format[0]["tool_calls"]), 1)
        self.assertEqual(llm_format[0]["tool_calls"][0]["id"], "call_123")
        self.assertEqual(llm_format[0]["tool_calls"][0]["function"]["name"], "read_file")
    
    def test_tool_result_conversion(self):
        """Test ToolResultObservation converts to tool role."""
        result = ToolResultObservation(
            session_id="test",
            sequence=1,
            call_id="call_123",
            content="file contents",
            status="success"
        )
        self.history.add(result)
        
        llm_format = self.history.to_llm_format()
        self.assertEqual(llm_format[0]["role"], "tool")
        self.assertEqual(llm_format[0]["tool_call_id"], "call_123")
        self.assertEqual(llm_format[0]["content"], "file contents")
    
    def test_error_observation_conversion(self):
        """Test ErrorObservation converts to user role with error prefix."""
        error = ErrorObservation(
            session_id="test",
            sequence=1,
            content="File not found"
        )
        self.history.add(error)
        
        llm_format = self.history.to_llm_format()
        self.assertEqual(llm_format[0]["role"], "user")
        self.assertIn("[Error]", llm_format[0]["content"])
        self.assertIn("File not found", llm_format[0]["content"])
    
    def test_environment_message_conversion(self):
        """Test EnvironmentMessage converts to user role."""
        env = EnvironmentMessage(
            session_id="test",
            sequence=1,
            event_type="file_changed",
            content="/test.txt modified"
        )
        self.history.add(env)
        
        llm_format = self.history.to_llm_format()
        self.assertEqual(llm_format[0]["role"], "user")
        self.assertIn("Environment Event", llm_format[0]["content"])
        self.assertIn("file_changed", llm_format[0]["content"])
    
    def test_complex_conversation(self):
        """Test full conversation flow."""
        # System prompt
        self.history.add(SystemMessage(session_id="s", sequence=0, content="You are helpful"))
        
        # User asks
        self.history.add(UserMessage(session_id="s", sequence=1, content="List files"))
        
        # LLM thinks
        self.history.add(LLMThinkMessage(session_id="s", sequence=2, content="I'll use ls"))
        
        # LLM calls tool
        tool_call = ToolCall(id="c1", tool_name="ls", arguments={"path": "."})
        self.history.add(ToolCallMessage(session_id="s", sequence=3, tool_calls=[tool_call]))
        
        # Tool responds
        self.history.add(ToolResultObservation(
            session_id="s", sequence=4, call_id="c1", content="file1.txt, file2.txt"
        ))
        
        # LLM responds
        self.history.add(LLMRespondMessage(session_id="s", sequence=5, content="Found 2 files"))
        
        llm_format = self.history.to_llm_format()
        self.assertEqual(len(llm_format), 6)
        
        # Verify order and roles
        self.assertEqual(llm_format[0]["role"], "system")
        self.assertEqual(llm_format[1]["role"], "user")
        self.assertEqual(llm_format[2]["role"], "assistant")  # think
        self.assertEqual(llm_format[3]["role"], "assistant")  # tool call
        self.assertEqual(llm_format[4]["role"], "tool")  # tool result
        self.assertEqual(llm_format[5]["role"], "assistant")  # respond


if __name__ == '__main__':
    unittest.main()
