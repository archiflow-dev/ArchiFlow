"""
Integration tests for ARCHIFLOW.md context ingestion in ProjectAgents.

Tests cover:
- ProjectAgent auto-enables context (default True)
- CodingAgent context loading
- CodingAgentV3 context loading (dynamic pattern)
- ResearchAgent context loading (static pattern)
- Context appears in correct position for different patterns
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../src')))

from agent_framework.llm.provider import LLMProvider, LLMResponse, FinishReason
from agent_framework.messages.types import (
    UserMessage,
    SystemMessage,
    ProjectContextMessage,
    ToolCallMessage,
    ToolCall,
)
from agent_framework.agents.coding_agent import CodingAgent
from agent_framework.agents.coding_agent_v3 import CodingAgentV3
from agent_framework.agents.research_agent import ResearchAgent
# Note: ProjectAgent is abstract - use concrete implementations like CodingAgent


class MockLLMProvider(LLMProvider):
    """Mock LLM provider for testing."""

    def __init__(self, model: str = "mock"):
        super().__init__(model)
        self.responses = []
        self.call_count = 0
        self.last_messages = None

    def add_response(self, content: str = None, tool_calls: list = None, finish_reason: FinishReason = FinishReason.STOP):
        """Add a canned response."""
        self.responses.append(LLMResponse(
            content=content,
            tool_calls=tool_calls or [],
            finish_reason=finish_reason,
            usage={"prompt_tokens": 10, "completion_tokens": 20}
        ))

    def generate(self, messages, tools=None, **kwargs):
        """Return next canned response and capture messages."""
        self.last_messages = messages
        if self.call_count >= len(self.responses):
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

    def count_tokens(self, messages):
        return 100

    def count_tools_tokens(self, tools_schema):
        return 50


class TestCodingAgentContext(unittest.TestCase):
    """Test suite for CodingAgent context loading."""

    def setUp(self):
        """Set up test fixtures."""
        self.session_id = "test_session"
        self.mock_llm = MockLLMProvider()

    def test_coding_agent_auto_enables_context(self):
        """Test that CodingAgent has include_project_context=True by default."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            archiflow_dir = tmpdir / ".archiflow"
            archiflow_dir.mkdir(parents=True)
            (archiflow_dir / "ARCHIFLOW.md").write_text("# Coding Standards\n- Use PEP 8")

            agent = CodingAgent(
                session_id=self.session_id,
                llm=self.mock_llm,
                project_directory=str(tmpdir)
            )

            # Verify context is enabled
            self.assertTrue(agent.include_project_context)
            self.assertIsNotNone(agent._project_context_msg)
            self.assertIn("Coding Standards", agent._project_context_msg.context)


class TestCodingAgentV3ContextDynamicPattern(unittest.TestCase):
    """Test suite for CodingAgentV3 context loading with dynamic pattern."""

    def setUp(self):
        """Set up test fixtures."""
        self.session_id = "test_session"
        self.mock_llm = MockLLMProvider()

    def test_coding_agent_v3_auto_enables_context(self):
        """Test that CodingAgentV3 has include_project_context=True by default."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            archiflow_dir = tmpdir / ".archiflow"
            archiflow_dir.mkdir(parents=True)
            (archiflow_dir / "ARCHIFLOW.md").write_text("# V3 Standards")

            agent = CodingAgentV3(
                session_id=self.session_id,
                llm=self.mock_llm,
                project_directory=str(tmpdir)
            )

            # Verify context is enabled
            self.assertTrue(agent.include_project_context)
            self.assertIsNotNone(agent._project_context_msg)

    def test_coding_agent_v3_context_position(self):
        """Test that context is at position 0 for dynamic pattern."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            archiflow_dir = tmpdir / ".archiflow"
            archiflow_dir.mkdir(parents=True)
            (archiflow_dir / "ARCHIFLOW.md").write_text("# V3 Standards")

            self.mock_llm.add_response(content="Hello!")

            agent = CodingAgentV3(
                session_id=self.session_id,
                llm=self.mock_llm,
                project_directory=str(tmpdir)
            )

            # Send first message
            agent.step(UserMessage(session_id=self.session_id, sequence=0, content="Hi"))

            # For dynamic pattern, context should be at position 0 in history
            messages = agent.history.get_messages()
            self.assertGreater(len(messages), 0)
            self.assertIsInstance(messages[0], ProjectContextMessage)

    def test_coding_agent_v3_llm_receives_correct_order(self):
        """Test that LLM receives messages in correct order for dynamic pattern."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            archiflow_dir = tmpdir / ".archiflow"
            archiflow_dir.mkdir(parents=True)
            (archiflow_dir / "ARCHIFLOW.md").write_text("# V3 Standards")

            self.mock_llm.add_response(content="Hello!")

            agent = CodingAgentV3(
                session_id=self.session_id,
                llm=self.mock_llm,
                project_directory=str(tmpdir)
            )

            # Send first message
            agent.step(UserMessage(session_id=self.session_id, sequence=0, content="Hi"))

            # Check what LLM received
            # Should be: [0] system (dynamic), [1] context, [2] user
            messages_sent = self.mock_llm.last_messages
            self.assertIsNotNone(messages_sent)
            self.assertGreaterEqual(len(messages_sent), 3)

            # First message should be system (prepended dynamically)
            self.assertEqual(messages_sent[0]["role"], "system")
            # Second message should be context (from history[0])
            self.assertEqual(messages_sent[1]["role"], "system")
            self.assertIn("V3 Standards", messages_sent[1]["content"])
            # Third message should be user
            self.assertEqual(messages_sent[2]["role"], "user")


class TestResearchAgentContextStaticPattern(unittest.TestCase):
    """Test suite for ResearchAgent context loading with static pattern."""

    def setUp(self):
        """Set up test fixtures."""
        self.session_id = "test_session"
        self.mock_llm = MockLLMProvider()

    def test_research_agent_auto_enables_context(self):
        """Test that ResearchAgent has include_project_context=True by default."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            archiflow_dir = tmpdir / ".archiflow"
            archiflow_dir.mkdir(parents=True)
            (archiflow_dir / "ARCHIFLOW.md").write_text("# Research Standards")

            agent = ResearchAgent(
                session_id=self.session_id,
                llm=self.mock_llm,
                project_directory=str(tmpdir)
            )

            # Verify context is enabled
            self.assertTrue(agent.include_project_context)
            self.assertIsNotNone(agent._project_context_msg)

    def test_research_agent_context_position(self):
        """Test that context is at position 1 for static pattern."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            archiflow_dir = tmpdir / ".archiflow"
            archiflow_dir.mkdir(parents=True)
            (archiflow_dir / "ARCHIFLOW.md").write_text("# Research Standards")

            self.mock_llm.add_response(content="Hello!")

            agent = ResearchAgent(
                session_id=self.session_id,
                llm=self.mock_llm,
                project_directory=str(tmpdir)
            )

            # Send first message
            agent.step(UserMessage(session_id=self.session_id, sequence=0, content="Hi"))

            # For static pattern, context should be at position 1 (after SystemMessage)
            messages = agent.history.get_messages()
            self.assertGreaterEqual(len(messages), 3)
            self.assertIsInstance(messages[0], SystemMessage)
            self.assertIsInstance(messages[1], ProjectContextMessage)
            self.assertIsInstance(messages[2], UserMessage)

    def test_research_agent_can_disable_context(self):
        """Test that ResearchAgent can disable context if explicitly set."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            archiflow_dir = tmpdir / ".archiflow"
            archiflow_dir.mkdir(parents=True)
            (archiflow_dir / "ARCHIFLOW.md").write_text("# Research Standards")

            agent = ResearchAgent(
                session_id=self.session_id,
                llm=self.mock_llm,
                project_directory=str(tmpdir),
                include_project_context=False
            )

            # Verify context is disabled
            self.assertFalse(agent.include_project_context)
            self.assertIsNone(agent._project_context_msg)


class TestContextConcatenation(unittest.TestCase):
    """Test suite for context concatenation from multiple sources."""

    def setUp(self):
        """Set up test fixtures."""
        self.session_id = "test_session"
        self.mock_llm = MockLLMProvider()

    def test_context_includes_sources_metadata(self):
        """Test that context includes sources metadata."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            archiflow_dir = tmpdir / ".archiflow"
            archiflow_dir.mkdir(parents=True)
            (archiflow_dir / "ARCHIFLOW.md").write_text("# Project Local\n\nLocal config")

            agent = CodingAgent(
                session_id=self.session_id,
                llm=self.mock_llm,
                project_directory=str(tmpdir)
            )

            # Verify context includes sources metadata
            self.assertIn("Project Local", agent._project_context_msg.context)
            self.assertGreater(len(agent._project_context_msg.sources), 0)
            # Sources should include the path to ARCHIFLOW.md
            self.assertTrue(any("ARCHIFLOW.md" in s for s in agent._project_context_msg.sources))


if __name__ == '__main__':
    unittest.main()
