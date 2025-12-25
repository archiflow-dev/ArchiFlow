"""
Unit tests for PromptRefinerAgent.
"""
import unittest
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../src')))

from agent_framework.agents.prompt_refiner_agent import PromptRefinerAgent
from agent_framework.messages.types import (
    UserMessage, ToolCallMessage, ToolResultObservation,
    LLMRespondMessage, AgentFinishedMessage, ToolCall
)
from agent_framework.llm.provider import LLMProvider, LLMResponse, FinishReason, ToolCallRequest
from agent_framework.tools.tool_base import ToolResult


class MockLLMProvider(LLMProvider):
    """Mock LLM provider for testing."""

    def __init__(self, model: str = "mock", **kwargs):
        super().__init__(model, **kwargs)
        self.responses = []
        self.call_count = 0

    def add_response(self, content: str = None, tool_calls: list = None, finish_reason: FinishReason = FinishReason.STOP):
        """Add a canned response."""
        self.responses.append(LLMResponse(
            content=content,
            tool_calls=tool_calls or [],
            finish_reason=finish_reason,
            usage={"prompt_tokens": 10, "completion_tokens": 20}
        ))

    def generate(self, messages, tools=None, **kwargs):
        """Return next canned response."""
        if self.call_count >= len(self.responses):
            # Default response if none configured
            return LLMResponse(
                content="Default mock response",
                finish_reason=FinishReason.STOP,
                usage={}
            )

        response = self.responses[self.call_count]
        self.call_count += 1
        return response

    def stream(self, messages, tools=None, **kwargs):
        """Not implemented for mock."""
        raise NotImplementedError()


class TestPromptRefinerAgent(unittest.TestCase):
    """Test suite for PromptRefinerAgent."""

    def setUp(self):
        """Set up test fixtures."""
        self.session_id = "test_refiner_session"
        self.mock_llm = MockLLMProvider()
        self.published_messages = []

        def publish_callback(msg):
            self.published_messages.append(msg)

        self.publish_callback = publish_callback

    def test_initialization_without_initial_prompt(self):
        """Test agent initialization without initial prompt."""
        agent = PromptRefinerAgent(
            session_id=self.session_id,
            llm=self.mock_llm,
            publish_callback=self.publish_callback,
            initial_prompt=None
        )

        self.assertEqual(agent.session_id, self.session_id)
        self.assertIsNone(agent.initial_prompt)
        self.assertTrue(agent.is_running)
        self.assertEqual(agent.sequence_counter, 1)  # System message added
        self.assertIsNotNone(agent.tools)

    def test_initialization_with_initial_prompt(self):
        """Test agent initialization with initial prompt."""
        initial_prompt = "Build a web app"

        agent = PromptRefinerAgent(
            session_id=self.session_id,
            llm=self.mock_llm,
            publish_callback=self.publish_callback,
            initial_prompt=initial_prompt
        )

        self.assertEqual(agent.initial_prompt, initial_prompt)
        self.assertTrue(agent.is_running)

    def test_tool_registration(self):
        """Test that required tools are registered."""
        agent = PromptRefinerAgent(
            session_id=self.session_id,
            llm=self.mock_llm,
            publish_callback=None,
            initial_prompt=None
        )

        tools = agent.tools.list_tools()
        tool_names = [t.name for t in tools]

        # Check for required tools
        required_tools = ["refine_prompt", "write", "read", "list", "finish_task"]
        for tool_name in required_tools:
            self.assertIn(
                tool_name,
                tool_names,
                f"Required tool '{tool_name}' not registered"
            )

        # Clipboard tool is optional (depends on pyperclip)
        # Just check it's either present or absent, both are valid
        has_clipboard = "copy_to_clipboard" in tool_names
        # Either way is fine, just document it
        if has_clipboard:
            print("  ✓ ClipboardTool registered (pyperclip available)")
        else:
            print("  ⚠ ClipboardTool not registered (pyperclip not installed)")

    def test_system_message_format(self):
        """Test that system message is properly formatted."""
        agent = PromptRefinerAgent(
            session_id=self.session_id,
            llm=self.mock_llm,
            publish_callback=None,
            initial_prompt=None
        )

        system_msg = agent.get_system_message()

        # Check key elements are in system message
        self.assertIn("Prompt Refinement Specialist", system_msg)
        self.assertIn("quality_score", system_msg)
        self.assertIn("refine_prompt", system_msg)
        self.assertIn(".archiflow/artifacts/refined_prompts/", system_msg)
        self.assertIn("copy_to_clipboard", system_msg)
        self.assertIn("finish_task", system_msg)

    def test_step_with_user_message_calls_llm(self):
        """Test that step() processes UserMessage and calls LLM."""
        self.mock_llm.add_response(content="I'll help you refine that prompt.")

        agent = PromptRefinerAgent(
            session_id=self.session_id,
            llm=self.mock_llm,
            publish_callback=self.publish_callback,
            initial_prompt=None
        )

        user_msg = UserMessage(
            session_id=self.session_id,
            sequence=2,
            content="Help me build a website"
        )

        response = agent.step(user_msg)

        # Should return LLMRespondMessage
        self.assertIsInstance(response, LLMRespondMessage)
        self.assertEqual(response.content, "I'll help you refine that prompt.")

        # Should have called LLM once
        self.assertEqual(self.mock_llm.call_count, 1)

        # Should have published response
        self.assertEqual(len(self.published_messages), 1)
        self.assertIsInstance(self.published_messages[0], LLMRespondMessage)

    def test_step_with_tool_call(self):
        """Test that step() handles tool calls."""
        # Mock LLM to return a tool call
        tool_call = ToolCallRequest(
            id="call_1",
            name="refine_prompt",
            arguments='{"prompt": "Fix the bug"}'
        )
        self.mock_llm.add_response(tool_calls=[tool_call])

        agent = PromptRefinerAgent(
            session_id=self.session_id,
            llm=self.mock_llm,
            publish_callback=self.publish_callback,
            initial_prompt=None
        )

        user_msg = UserMessage(
            session_id=self.session_id,
            sequence=2,
            content="Fix the bug"
        )

        response = agent.step(user_msg)

        # Should return ToolCallMessage
        self.assertIsInstance(response, ToolCallMessage)
        self.assertEqual(len(response.tool_calls), 1)
        self.assertEqual(response.tool_calls[0].tool_name, "refine_prompt")

        # Should have published tool call
        self.assertEqual(len(self.published_messages), 1)
        self.assertIsInstance(self.published_messages[0], ToolCallMessage)

    def test_step_with_finish_task(self):
        """Test that step() detects finish_task and stops agent."""
        # Mock LLM to return finish_task call
        tool_call = ToolCallRequest(
            id="call_finish",
            name="finish_task",
            arguments='{"reason": "Refinement complete"}'
        )
        self.mock_llm.add_response(tool_calls=[tool_call])

        agent = PromptRefinerAgent(
            session_id=self.session_id,
            llm=self.mock_llm,
            publish_callback=self.publish_callback,
            initial_prompt=None
        )

        user_msg = UserMessage(
            session_id=self.session_id,
            sequence=2,
            content="Thanks!"
        )

        response = agent.step(user_msg)

        # Agent should be stopped
        self.assertFalse(agent.is_running)

        # Should have published AgentFinishedMessage
        finished_msgs = [m for m in self.published_messages if isinstance(m, AgentFinishedMessage)]
        self.assertEqual(len(finished_msgs), 1)
        self.assertEqual(finished_msgs[0].reason, "Refinement complete")

    def test_agent_stops_when_running_false(self):
        """Test that agent returns None when not running."""
        agent = PromptRefinerAgent(
            session_id=self.session_id,
            llm=self.mock_llm,
            publish_callback=None,
            initial_prompt=None
        )

        # Stop agent
        agent.is_running = False

        user_msg = UserMessage(
            session_id=self.session_id,
            sequence=2,
            content="Test message"
        )

        response = agent.step(user_msg)

        # Should return None and not call LLM
        self.assertIsNone(response)
        self.assertEqual(self.mock_llm.call_count, 0)

    def test_sequence_counter_increments(self):
        """Test that sequence counter increments correctly."""
        self.mock_llm.add_response(content="Response 1")
        self.mock_llm.add_response(content="Response 2")

        agent = PromptRefinerAgent(
            session_id=self.session_id,
            llm=self.mock_llm,
            publish_callback=self.publish_callback,
            initial_prompt=None
        )

        initial_seq = agent.sequence_counter

        # First message
        msg1 = UserMessage(
            session_id=self.session_id,
            sequence=2,
            content="Message 1"
        )
        agent.step(msg1)

        # Sequence should have incremented
        self.assertGreater(agent.sequence_counter, initial_seq)

        seq_after_first = agent.sequence_counter

        # Second message
        msg2 = UserMessage(
            session_id=self.session_id,
            sequence=4,
            content="Message 2"
        )
        agent.step(msg2)

        # Sequence should have incremented again
        self.assertGreater(agent.sequence_counter, seq_after_first)

    def test_memory_update_with_messages(self):
        """Test that messages are added to history."""
        self.mock_llm.add_response(content="Test response")

        agent = PromptRefinerAgent(
            session_id=self.session_id,
            llm=self.mock_llm,
            publish_callback=None,
            initial_prompt=None
        )

        # Check initial history (should have system message)
        initial_history_size = len(agent.history.to_llm_format())

        user_msg = UserMessage(
            session_id=self.session_id,
            sequence=2,
            content="Test prompt"
        )

        agent.step(user_msg)

        # History should have grown
        new_history_size = len(agent.history.to_llm_format())
        self.assertGreater(new_history_size, initial_history_size)

    def test_error_handling_in_step(self):
        """Test that step() handles LLM errors gracefully."""
        # Create a mock LLM that throws an exception
        class FailingMockLLM(MockLLMProvider):
            def generate(self, messages, tools=None, **kwargs):
                raise Exception("LLM error")

        failing_llm = FailingMockLLM()

        agent = PromptRefinerAgent(
            session_id=self.session_id,
            llm=failing_llm,
            publish_callback=self.publish_callback,
            initial_prompt=None
        )

        user_msg = UserMessage(
            session_id=self.session_id,
            sequence=2,
            content="Test message"
        )

        response = agent.step(user_msg)

        # Should return error message, not crash
        self.assertIsInstance(response, LLMRespondMessage)
        self.assertIn("error", response.content.lower())

    def test_config_values(self):
        """Test that agent config is properly set."""
        agent = PromptRefinerAgent(
            session_id=self.session_id,
            llm=self.mock_llm,
            publish_callback=None,
            initial_prompt=None
        )

        # Check config through BaseAgent
        self.assertEqual(agent.session_id, self.session_id)
        # Agent should have proper name
        self.assertIsNotNone(agent.llm)


class TestPromptRefinerAgentIntegration(unittest.TestCase):
    """Integration tests for PromptRefinerAgent workflow."""

    def setUp(self):
        """Set up test fixtures."""
        self.session_id = "integration_test"
        self.mock_llm = MockLLMProvider()
        self.published_messages = []

        def publish_callback(msg):
            self.published_messages.append(msg)

        self.publish_callback = publish_callback

    def test_multi_turn_conversation(self):
        """Test multi-turn refinement conversation."""
        # Simulate a conversation:
        # User: "Build a web app"
        # Agent: calls refine_prompt tool
        # Agent: asks follow-up questions
        # User: answers
        # Agent: refines further
        # Agent: finishes

        # Response 1: Agent calls refine_prompt
        tool_call_1 = ToolCallRequest(
            id="call_refine",
            name="refine_prompt",
            arguments='{"prompt": "Build a web app"}'
        )
        self.mock_llm.add_response(tool_calls=[tool_call_1])

        # Response 2: Agent asks questions
        self.mock_llm.add_response(
            content="I analyzed your prompt. What specific features should the web app have?"
        )

        # Response 3: Agent calls finish_task
        tool_call_finish = ToolCallRequest(
            id="call_finish",
            name="finish_task",
            arguments='{"reason": "Refinement complete"}'
        )
        self.mock_llm.add_response(tool_calls=[tool_call_finish])

        agent = PromptRefinerAgent(
            session_id=self.session_id,
            llm=self.mock_llm,
            publish_callback=self.publish_callback,
            initial_prompt="Build a web app"
        )

        # Turn 1: User message
        msg1 = UserMessage(
            session_id=self.session_id,
            sequence=2,
            content="Build a web app"
        )
        response1 = agent.step(msg1)
        self.assertIsInstance(response1, ToolCallMessage)
        self.assertTrue(agent.is_running)

        # Turn 2: Tool result
        tool_result = ToolResultObservation(
            session_id=self.session_id,
            sequence=4,
            call_id="call_refine",
            content='{"quality_score": 5.0, "refined_prompt": "Build a web application with..."}',
            status="success"
        )
        response2 = agent.step(tool_result)
        self.assertIsInstance(response2, LLMRespondMessage)
        self.assertTrue(agent.is_running)

        # Turn 3: User answer
        msg3 = UserMessage(
            session_id=self.session_id,
            sequence=6,
            content="E-commerce features with payment integration"
        )
        response3 = agent.step(msg3)
        # Agent called finish_task, should return AgentFinishedMessage
        # Note: In practice, PromptRefinerAgent._process_tool_calls() returns
        # ToolCallMessage first, then publishes AgentFinishedMessage separately
        # But the response can be either depending on the flow
        self.assertTrue(
            isinstance(response3, (ToolCallMessage, AgentFinishedMessage)),
            f"Expected ToolCallMessage or AgentFinishedMessage, got {type(response3)}"
        )
        self.assertFalse(agent.is_running)  # finish_task called

        # Check published messages - should have at least AgentFinishedMessage
        finished_msgs = [m for m in self.published_messages if isinstance(m, AgentFinishedMessage)]
        self.assertGreater(len(finished_msgs), 0, "Should have published AgentFinishedMessage")
        self.assertGreater(len(self.published_messages), 0)


if __name__ == '__main__':
    unittest.main()
