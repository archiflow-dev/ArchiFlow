"""
Unit tests for AgentSession.
"""
import unittest
import sys
import os
import tempfile
import shutil
import json

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from src.agent_framework.controller.session import AgentSession, SessionState
from src.agent_framework.agents.base import SimpleAgent
from src.agent_framework.messages.types import (
    UserMessage, ToolCallMessage, ToolResultObservation,
    LLMRespondMessage, ToolCall, StopMessage
)
from src.agent_framework.llm.provider import LLMProvider, LLMResponse, FinishReason, ToolCallRequest


class MockLLMProvider(LLMProvider):
    """Mock LLM for testing."""

    def __init__(self, model: str = "mock", **kwargs):
        super().__init__(model, **kwargs)
        self.responses = []
        self.call_count = 0

    def add_response(self, content: str = None, tool_calls: list = None):
        self.responses.append(LLMResponse(
            content=content,
            tool_calls=tool_calls or [],
            finish_reason=FinishReason.STOP if not tool_calls else FinishReason.TOOL_CALLS,
            usage={}
        ))

    def generate(self, messages, tools=None, **kwargs):
        if self.call_count >= len(self.responses):
            return LLMResponse(content="Default response", finish_reason=FinishReason.STOP, usage={})
        response = self.responses[self.call_count]
        self.call_count += 1
        return response

    def stream(self, messages, tools=None, **kwargs):
        raise NotImplementedError()


class TestAgentSession(unittest.TestCase):
    """Test suite for AgentSession."""

    def setUp(self):
        """Set up test fixtures."""
        self.session_id = "test_session_123"
        self.user_id = "user_456"

        # Create mock agent
        self.mock_llm = MockLLMProvider()
        self.agent = SimpleAgent(
            session_id=self.session_id,
            llm=self.mock_llm
        )

        # Create session
        self.session = AgentSession(
            session_id=self.session_id,
            user_id=self.user_id,
            agent=self.agent,
            inbox_topic=f"session/{self.session_id}/inbox",
            outbox_topic=f"session/{self.session_id}/outbox"
        )

        # Track output messages
        self.output_messages = []

        def output_callback(msg):
            self.output_messages.append(msg)

        self.session.subscribe_output(output_callback)

    def test_initialization(self):
        """Test session initialization."""
        self.assertEqual(self.session.session_id, self.session_id)
        self.assertEqual(self.session.user_id, self.user_id)
        self.assertEqual(self.session.state, SessionState.ACTIVE)
        self.assertEqual(self.session.message_count, 0)
        self.assertIsNotNone(self.session.created_at)
        self.assertIsNotNone(self.session.last_active)

    def test_send_message(self):
        """Test sending user message to agent."""
        self.mock_llm.add_response(content="Hello! How can I help?")

        self.session.send_message("Hi there")

        # Check message was sent
        self.assertEqual(self.session.message_count, 1)

        # Check output was received
        self.assertEqual(len(self.output_messages), 1)
        self.assertIsInstance(self.output_messages[0], LLMRespondMessage)
        self.assertEqual(self.output_messages[0].content, "Hello! How can I help?")

    def test_send_message_increments_sequence(self):
        """Test that message sequence increments."""
        self.mock_llm.add_response(content="Response 1")
        self.mock_llm.add_response(content="Response 2")

        self.session.send_message("Message 1")
        self.session.send_message("Message 2")

        self.assertEqual(self.session.message_count, 2)

    def test_send_message_when_paused(self):
        """Test sending message to paused session fails."""
        self.session.pause()

        with self.assertRaises(ValueError) as ctx:
            self.session.send_message("Test")

        self.assertIn("paused", str(ctx.exception))

    def test_send_message_when_stopped(self):
        """Test sending message to stopped session fails."""
        self.session.stop()

        with self.assertRaises(ValueError) as ctx:
            self.session.send_message("Test")

        self.assertIn("stopped", str(ctx.exception))

    def test_subscribe_output(self):
        """Test subscribing to output."""
        messages_received = []

        def callback(msg):
            messages_received.append(msg)

        self.session.subscribe_output(callback)

        self.mock_llm.add_response(content="Test response")
        self.session.send_message("Test")

        # Both callbacks should receive message
        self.assertEqual(len(self.output_messages), 1)
        self.assertEqual(len(messages_received), 1)

    def test_validate_tool_call_no_restrictions(self):
        """Test tool validation with no restrictions (all allowed)."""
        tool_call_msg = ToolCallMessage(
            session_id=self.session_id,
            sequence=1,
            tool_calls=[
                ToolCall(id="1", tool_name="read_file", arguments={"path": "/tmp/test"})
            ]
        )

        # No restrictions, should be valid
        self.assertTrue(self.session.validate_tool_call(tool_call_msg))

    def test_validate_tool_call_with_allowed_list(self):
        """Test tool validation with allowed list."""
        # Create session with tool restrictions
        session = AgentSession(
            session_id="restricted_session",
            user_id=self.user_id,
            agent=self.agent,
            inbox_topic="test/inbox",
            outbox_topic="test/outbox",
            allowed_tools={"read_file", "write_file"}
        )

        # Allowed tool
        allowed_msg = ToolCallMessage(
            session_id="restricted_session",
            sequence=1,
            tool_calls=[
                ToolCall(id="1", tool_name="read_file", arguments={})
            ]
        )
        self.assertTrue(session.validate_tool_call(allowed_msg))

        # Disallowed tool
        disallowed_msg = ToolCallMessage(
            session_id="restricted_session",
            sequence=2,
            tool_calls=[
                ToolCall(id="2", tool_name="execute_code", arguments={})
            ]
        )
        self.assertFalse(session.validate_tool_call(disallowed_msg))

    def test_validate_tool_call_multiple_tools(self):
        """Test validation with multiple tool calls."""
        session = AgentSession(
            session_id="multi_session",
            user_id=self.user_id,
            agent=self.agent,
            inbox_topic="test/inbox",
            outbox_topic="test/outbox",
            allowed_tools={"read_file", "write_file"}
        )

        # All allowed
        all_allowed = ToolCallMessage(
            session_id="multi_session",
            sequence=1,
            tool_calls=[
                ToolCall(id="1", tool_name="read_file", arguments={}),
                ToolCall(id="2", tool_name="write_file", arguments={})
            ]
        )
        self.assertTrue(session.validate_tool_call(all_allowed))

        # One disallowed
        one_disallowed = ToolCallMessage(
            session_id="multi_session",
            sequence=2,
            tool_calls=[
                ToolCall(id="3", tool_name="read_file", arguments={}),
                ToolCall(id="4", tool_name="delete_file", arguments={})
            ]
        )
        self.assertFalse(session.validate_tool_call(one_disallowed))

    def test_pause_and_resume(self):
        """Test pausing and resuming session."""
        self.assertEqual(self.session.state, SessionState.ACTIVE)

        self.session.pause()
        self.assertEqual(self.session.state, SessionState.PAUSED)

        self.session.resume()
        self.assertEqual(self.session.state, SessionState.ACTIVE)

    def test_stop(self):
        """Test stopping session."""
        self.session.stop("Test stop")

        self.assertEqual(self.session.state, SessionState.STOPPED)

        # Agent should have received stop message
        self.assertFalse(self.agent.is_running)

    def test_send_tool_result(self):
        """Test sending tool result to agent."""
        self.mock_llm.add_response(content="File contents: Hello World")

        tool_result = ToolResultObservation(
            session_id=self.session_id,
            sequence=1,
            call_id="call_123",
            content="Hello World",
            status="success"
        )

        self.session.send_tool_result(tool_result)

        # Check agent processed it
        self.assertEqual(len(self.output_messages), 1)
        self.assertIn("Hello World", self.output_messages[0].content)

    def test_get_metadata(self):
        """Test getting session metadata."""
        metadata = self.session.get_metadata()

        self.assertEqual(metadata["session_id"], self.session_id)
        self.assertEqual(metadata["user_id"], self.user_id)
        self.assertEqual(metadata["state"], "active")
        self.assertEqual(metadata["message_count"], 0)
        self.assertIsNotNone(metadata["created_at"])
        self.assertIsNotNone(metadata["last_active"])
        self.assertEqual(metadata["agent_name"], "SimpleAgent")

    def test_tool_call_validation_blocks_invalid(self):
        """Test that invalid tool calls are blocked from output."""
        # Create session with restrictions
        session = AgentSession(
            session_id="blocked_session",
            user_id=self.user_id,
            agent=self.agent,
            inbox_topic="test/inbox",
            outbox_topic="test/outbox",
            allowed_tools={"read_file"}
        )

        output_messages = []
        session.subscribe_output(lambda msg: output_messages.append(msg))

        # Mock LLM returns disallowed tool
        self.mock_llm.add_response(
            tool_calls=[
                ToolCallRequest(id="1", name="execute_code", arguments="{}")
            ]
        )

        # Create new agent for this session
        agent = SimpleAgent(session_id="blocked_session", llm=self.mock_llm)
        session.agent = agent
        session.agent.publish_callback = session._on_agent_output

        # Send message that triggers tool call
        user_msg = UserMessage(
            session_id="blocked_session",
            sequence=0,
            content="Run some code"
        )
        agent.step(user_msg)

        # Tool call should be blocked (not in output)
        self.assertEqual(len(output_messages), 0)


class TestAgentSessionPersistence(unittest.TestCase):
    """Test session state persistence."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test files."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_save_state(self):
        """Test saving session state."""
        session_id = "persist_session"
        user_id = "user_123"

        mock_llm = MockLLMProvider()
        agent = SimpleAgent(session_id=session_id, llm=mock_llm)

        session = AgentSession(
            session_id=session_id,
            user_id=user_id,
            agent=agent,
            inbox_topic=f"session/{session_id}/inbox",
            outbox_topic=f"session/{session_id}/outbox",
            allowed_tools={"read_file", "write_file"},
            state_dir=self.temp_dir
        )

        # Save state
        session.save_state()

        # Check file exists
        state_file = os.path.join(self.temp_dir, f"{session_id}.json")
        self.assertTrue(os.path.exists(state_file))

        # Check contents
        with open(state_file, 'r') as f:
            state_data = json.load(f)

        self.assertEqual(state_data["session_id"], session_id)
        self.assertEqual(state_data["user_id"], user_id)
        self.assertEqual(state_data["state"], "active")
        self.assertIsNotNone(state_data["created_at"])

    def test_load_state(self):
        """Test loading session state."""
        session_id = "load_session"
        user_id = "user_456"

        # Create and save a session
        mock_llm = MockLLMProvider()
        agent = SimpleAgent(session_id=session_id, llm=mock_llm)

        original_session = AgentSession(
            session_id=session_id,
            user_id=user_id,
            agent=agent,
            inbox_topic=f"session/{session_id}/inbox",
            outbox_topic=f"session/{session_id}/outbox",
            allowed_tools={"read_file"},
            state_dir=self.temp_dir
        )

        # Send some messages
        mock_llm.add_response(content="Response 1")
        original_session.send_message("Test 1")

        original_session.save_state()

        # Load it back
        new_agent = SimpleAgent(session_id=session_id, llm=MockLLMProvider())
        loaded_session = AgentSession.load_state(
            session_id=session_id,
            state_dir=self.temp_dir,
            agent=new_agent
        )

        # Verify loaded state
        self.assertEqual(loaded_session.session_id, session_id)
        self.assertEqual(loaded_session.user_id, user_id)
        self.assertEqual(loaded_session.message_count, 1)
        self.assertEqual(loaded_session.allowed_tools, {"read_file"})

    def test_load_nonexistent_session(self):
        """Test loading non-existent session fails."""
        mock_llm = MockLLMProvider()
        agent = SimpleAgent(session_id="test", llm=mock_llm)

        with self.assertRaises(FileNotFoundError):
            AgentSession.load_state(
                session_id="nonexistent",
                state_dir=self.temp_dir,
                agent=agent
            )

    def test_save_without_state_dir(self):
        """Test save_state with no state_dir configured."""
        session_id = "no_state_session"
        mock_llm = MockLLMProvider()
        agent = SimpleAgent(session_id=session_id, llm=mock_llm)

        session = AgentSession(
            session_id=session_id,
            user_id="user_123",
            agent=agent,
            inbox_topic="test/inbox",
            outbox_topic="test/outbox",
            state_dir=None  # No state dir
        )

        # Should not raise, just log warning
        session.save_state()


if __name__ == '__main__':
    unittest.main()
