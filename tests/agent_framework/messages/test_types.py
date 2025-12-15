"""Tests for message types."""
import unittest
import time
from src.agent_framework.messages.types import (
    UserMessage, SystemMessage, EnvironmentMessage,
    LLMThinkMessage, LLMRespondMessage,
    ToolCallMessage, ToolCall,
    ToolResultObservation, ErrorObservation, StopMessage,
    deserialize_message
)


class TestMessageSerialization(unittest.TestCase):
    """Test message serialization and deserialization."""
    
    def test_user_message(self):
        """Test UserMessage serialization."""
        msg = UserMessage(
            session_id="test_session",
            sequence=1,
            content="Hello, agent!"
        )
        
        # To dict
        data = msg.to_dict()
        self.assertEqual(data['session_id'], "test_session")
        self.assertEqual(data['sequence'], 1)
        self.assertEqual(data['content'], "Hello, agent!")
        self.assertEqual(data['source'], "user")
        
        # From dict
        msg2 = UserMessage.from_dict(data)
        self.assertEqual(msg2.session_id, msg.session_id)
        self.assertEqual(msg2.content, msg.content)
    
    def test_system_message(self):
        """Test SystemMessage."""
        msg = SystemMessage(
            session_id="test",
            sequence=0,
            content="System initialized"
        )
        
        data = msg.to_dict()
        msg2 = SystemMessage.from_dict(data)
        self.assertEqual(msg2.content, msg.content)
    
    def test_environment_message(self):
        """Test EnvironmentMessage."""
        msg = EnvironmentMessage(
            session_id="test",
            sequence=5,
            event_type="file_changed",
            content={"path": "/file.txt"}
        )
        
        data = msg.to_dict()
        self.assertEqual(data['event_type'], "file_changed")
        
        msg2 = EnvironmentMessage.from_dict(data)
        self.assertEqual(msg2.event_type, "file_changed")
        self.assertEqual(msg2.content, {"path": "/file.txt"})
    
    def test_llm_think_message(self):
        """Test LLMThinkMessage."""
        msg = LLMThinkMessage(
            session_id="test",
            sequence=2,
            content="I need to check the directory..."
        )
        
        data = msg.to_dict()
        msg2 = LLMThinkMessage.from_dict(data)
        self.assertEqual(msg2.content, msg.content)
    
    def test_llm_respond_message(self):
        """Test LLMRespondMessage."""
        msg = LLMRespondMessage(
            session_id="test",
            sequence=10,
            content="Task completed!"
        )
        
        data = msg.to_dict()
        msg2 = LLMRespondMessage.from_dict(data)
        self.assertEqual(msg2.content, msg.content)
    
    def test_tool_call_message(self):
        """Test ToolCallMessage with multiple tool calls."""
        tool_call1 = ToolCall(
            id="call_1",
            tool_name="read_file",
            arguments={"path": "/test.txt"}
        )
        tool_call2 = ToolCall(
            id="call_2",
            tool_name="list_files",
            arguments={"path": "."}
        )
        
        msg = ToolCallMessage(
            session_id="test",
            sequence=3,
            tool_calls=[tool_call1, tool_call2]
        )
        
        data = msg.to_dict()
        self.assertEqual(len(data['tool_calls']), 2)
        self.assertEqual(data['tool_calls'][0]['tool_name'], "read_file")
        
        msg2 = ToolCallMessage.from_dict(data)
        self.assertEqual(len(msg2.tool_calls), 2)
        self.assertEqual(msg2.tool_calls[0].tool_name, "read_file")
        self.assertEqual(msg2.tool_calls[1].arguments, {"path": "."})
    
    def test_tool_result_observation(self):
        """Test ToolResultObservation."""
        msg = ToolResultObservation(
            session_id="test",
            sequence=4,
            call_id="call_1",
            content="file contents here",
            status="success"
        )
        
        data = msg.to_dict()
        msg2 = ToolResultObservation.from_dict(data)
        self.assertEqual(msg2.call_id, "call_1")
        self.assertEqual(msg2.status, "success")
    
    def test_error_observation(self):
        """Test ErrorObservation."""
        msg = ErrorObservation(
            session_id="test",
            sequence=5,
            content="File not found",
            traceback="Traceback..."
        )
        
        data = msg.to_dict()
        msg2 = ErrorObservation.from_dict(data)
        self.assertEqual(msg2.content, "File not found")
        self.assertEqual(msg2.traceback, "Traceback...")
    
    def test_stop_message(self):
        """Test StopMessage."""
        msg = StopMessage(
            session_id="test",
            sequence=100,
            reason="Max iterations reached"
        )
        
        data = msg.to_dict()
        msg2 = StopMessage.from_dict(data)
        self.assertEqual(msg2.reason, "Max iterations reached")


class TestMessageType(unittest.TestCase):
    """Test message type property."""
    
    def test_message_types(self):
        """Verify all messages have correct type property."""
        msg1 = UserMessage(session_id="test", sequence=1, content="Hi")
        self.assertEqual(msg1.type, "UserMessage")
        
        msg2 = LLMThinkMessage(session_id="test", sequence=2, content="Thinking...")
        self.assertEqual(msg2.type, "LLMThinkMessage")
        
        msg3 = ToolCallMessage(session_id="test", sequence=3)
        self.assertEqual(msg3.type, "ToolCallMessage")


class TestDeserializeMessage(unittest.TestCase):
    """Test generic message deserialization."""
    
    def test_deserialize_user_message(self):
        """Test deserializing UserMessage."""
        data = {
            'type': 'UserMessage',
            'session_id': 'test',
            'sequence': 1,
            'timestamp': time.time(),
            'message_id': '12345',
            'content': 'Hello',
            'source': 'user'
        }
        
        msg = deserialize_message(data)
        self.assertIsInstance(msg, UserMessage)
        self.assertEqual(msg.content, 'Hello')
    
    def test_deserialize_tool_call_message(self):
        """Test deserializing ToolCallMessage."""
        data = {
            'type': 'ToolCallMessage',
            'session_id': 'test',
            'sequence': 2,
            'timestamp': time.time(),
            'message_id': '67890',
            'tool_calls': [
                {'id': 'call_1', 'tool_name': 'ls', 'arguments': {'path': '.'}}
            ]
        }
        
        msg = deserialize_message(data)
        self.assertIsInstance(msg, ToolCallMessage)
        self.assertEqual(len(msg.tool_calls), 1)
        self.assertEqual(msg.tool_calls[0].tool_name, 'ls')
    
    def test_deserialize_missing_type(self):
        """Test error when type is missing."""
        data = {'session_id': 'test', 'sequence': 1}
        
        with self.assertRaises(ValueError) as context:
            deserialize_message(data)
        self.assertIn("missing 'type'", str(context.exception))
    
    def test_deserialize_unknown_type(self):
        """Test error with unknown type."""
        data = {'type': 'UnknownMessage', 'session_id': 'test'}
        
        with self.assertRaises(ValueError) as context:
            deserialize_message(data)
        self.assertIn("Unknown message type", str(context.exception))


class TestMessageDefaults(unittest.TestCase):
    """Test message default values."""
    
    def test_timestamp_auto_generated(self):
        """Test that timestamp is auto-generated."""
        before = time.time()
        msg = UserMessage(session_id="test", sequence=1, content="Hi")
        after = time.time()
        
        self.assertGreaterEqual(msg.timestamp, before)
        self.assertLessEqual(msg.timestamp, after)
    
    def test_message_id_auto_generated(self):
        """Test that message_id is auto-generated."""
        msg1 = UserMessage(session_id="test", sequence=1, content="Hi")
        msg2 = UserMessage(session_id="test", sequence=2, content="Hello")
        
        self.assertIsNotNone(msg1.message_id)
        self.assertIsNotNone(msg2.message_id)
        self.assertNotEqual(msg1.message_id, msg2.message_id)
    
    def test_stop_message_default_reason(self):
        """Test StopMessage default reason."""
        msg = StopMessage(session_id="test", sequence=1)
        self.assertEqual(msg.reason, "User requested stop")


if __name__ == '__main__':
    unittest.main()
