import unittest
from unittest.mock import MagicMock, ANY
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../src')))

from agent_framework.agent_controller import AgentController
from agent_framework.context import TopicContext
from agent_framework.messages.types import (
    UserMessage, ToolCallMessage, ToolResultObservation, WaitForUserInput, AgentFinishedMessage
)
from message_queue.broker import MessageBroker

class TestAgentController(unittest.TestCase):
    def setUp(self):
        self.mock_agent = MagicMock()
        self.mock_broker = MagicMock(spec=MessageBroker)
        self.context = TopicContext.default("test_session")
        self.controller = AgentController(self.mock_agent, self.mock_broker, self.context)

    def test_initialization(self):
        self.assertEqual(self.controller.context.agent_topic, "agent.test_session")
        # Verify callback registration
        self.mock_agent.set_publish_callback.assert_called_once()

    def test_on_event_user_input(self):
        # Simulate receiving a USER_INPUT message
        message = MagicMock()
        message.payload = {"type": "USER_INPUT", "content": "Hello"}
        
        self.controller.on_event(message)
        
        # Verify agent step was called
        self.mock_agent.step.assert_called_with({"input": {"type": "USER_INPUT", "content": "Hello"}})

    def test_handle_agent_response_wait_for_input(self):
        # Simulate agent returning WaitForUserInput
        response = WaitForUserInput(session_id="test_session", sequence=1)
        self.mock_agent.step.return_value = response
        
        # Trigger event to drive the loop
        message = MagicMock()
        message.payload = {"type": "USER_INPUT"}
        self.controller.on_event(message)
        
        # Verify broker published to client topic
        self.mock_broker.publish.assert_called_with(
            self.context.client_topic,
            {
                "type": "WAIT_FOR_USER_INPUT",
                "session_id": "test_session",
                "sequence": 1
            }
        )

    def test_handle_agent_response_tool_call(self):
        # Simulate agent returning ToolCallMessage
        tool_call = MagicMock()
        tool_call.tool_name = "test_tool"
        tool_call.arguments = {}
        
        response = ToolCallMessage(
            session_id="test_session", 
            sequence=1, 
            tool_calls=[tool_call]
        )
        self.mock_agent.step.return_value = response
        
        # Trigger event
        message = MagicMock()
        message.payload = {"type": "USER_INPUT"}
        self.controller.on_event(message)
        
        # Verify broker published to RUNTIME topic
        self.mock_broker.publish.assert_called_with(
            self.context.runtime_topic,
            {
                "type": "TOOL_EXECUTION_REQUEST",
                "session_id": "test_session",
                "tool_calls": [tool_call]
            }
        )

if __name__ == '__main__':
    unittest.main()
