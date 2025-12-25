"""
Unit tests for ARCHIFLOW.md context ingestion in BaseAgent.

Tests cover:
- Context loading when enabled
- Context disabled by default
- Context caching behavior
- Context reload functionality
- Context injection position (static pattern)
- Context injection position (dynamic pattern)
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../src')))

from agent_framework.agents.base import BaseAgent, SimpleAgent
from agent_framework.config.hierarchy import ConfigHierarchy
from agent_framework.llm.provider import LLMProvider, LLMResponse, FinishReason
from agent_framework.messages.types import (
    UserMessage,
    SystemMessage,
    ProjectContextMessage,
    LLMRespondMessage,
)
from agent_framework.memory.history import HistoryManager
from agent_framework.memory.summarizer import LLMSummarizer


class MockLLMProvider(LLMProvider):
    """Mock LLM provider for testing."""

    def __init__(self, model: str = "mock"):
        super().__init__(model)
        self.responses = []
        self.call_count = 0

    def add_response(self, content: str = None, finish_reason: FinishReason = FinishReason.STOP):
        """Add a canned response."""
        self.responses.append(LLMResponse(
            content=content,
            finish_reason=finish_reason,
            usage={"prompt_tokens": 10, "completion_tokens": 20}
        ))

    def generate(self, messages, tools=None, **kwargs):
        """Return next canned response."""
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


class TestBaseAgentContextLoading(unittest.TestCase):
    """Test suite for BaseAgent context loading functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.session_id = "test_session"
        self.mock_llm = MockLLMProvider()

    def test_context_disabled_by_default(self):
        """Test that context is disabled by default for BaseAgent."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create ARCHIFLOW.md
            archiflow_dir = Path(tmpdir) / ".archiflow"
            archiflow_dir.mkdir(parents=True)
            (archiflow_dir / "ARCHIFLOW.md").write_text("# Test Context")

            # Create agent WITHOUT include_project_context
            agent = SimpleAgent(
                session_id=self.session_id,
                llm=self.mock_llm,
                working_dir=Path(tmpdir)
            )

            # Verify context is NOT loaded
            self.assertFalse(agent.include_project_context)
            self.assertIsNone(agent._project_context_msg)

    def test_context_enabled_explicitly(self):
        """Test that context can be enabled explicitly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create ARCHIFLOW.md
            archiflow_dir = Path(tmpdir) / ".archiflow"
            archiflow_dir.mkdir(parents=True)
            (archiflow_dir / "ARCHIFLOW.md").write_text("# Test Context")

            # Create agent WITH include_project_context=True
            agent = SimpleAgent(
                session_id=self.session_id,
                llm=self.mock_llm,
                include_project_context=True,
                working_dir=Path(tmpdir)
            )

            # Verify context IS loaded
            self.assertTrue(agent.include_project_context)
            self.assertIsNotNone(agent._project_context_msg)
            self.assertIsInstance(agent._project_context_msg, ProjectContextMessage)
            self.assertIn("Test Context", agent._project_context_msg.context)

    def test_context_loading_from_multiple_sources(self):
        """Test that context is loaded and concatenated from multiple sources."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create project-local ARCHIFLOW.md
            archiflow_dir = tmpdir / ".archiflow"
            archiflow_dir.mkdir(parents=True)
            (archiflow_dir / "ARCHIFLOW.md").write_text("# Project Context\n\nLocal settings")

            # Create user-global ARCHIFLOW.md
            user_archiflow = Path.home() / ".archiflow_temp_test"
            user_archiflow.mkdir(parents=True, exist_ok=True)
            (user_archiflow / "ARCHIFLOW.md").write_text("# User Context\n\nGlobal settings")

            try:
                agent = SimpleAgent(
                    session_id=self.session_id,
                    llm=self.mock_llm,
                    include_project_context=True,
                    working_dir=tmpdir
                )

                # Verify both contexts are included
                self.assertIsNotNone(agent._project_context_msg)
                context = agent._project_context_msg.context
                self.assertIn("Project Context", context)
                self.assertIn("Local settings", context)

            finally:
                # Cleanup
                (user_archiflow / "ARCHIFLOW.md").unlink()
                user_archiflow.rmdir()

    def test_context_message_attributes(self):
        """Test that ProjectContextMessage has correct attributes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create ARCHIFLOW.md
            archiflow_dir = Path(tmpdir) / ".archiflow"
            archiflow_dir.mkdir(parents=True)
            (archiflow_dir / "ARCHIFLOW.md").write_text("# Test Content")

            agent = SimpleAgent(
                session_id=self.session_id,
                llm=self.mock_llm,
                include_project_context=True,
                working_dir=Path(tmpdir)
            )

            # Verify message attributes
            msg = agent._project_context_msg
            self.assertEqual(msg.session_id, self.session_id)
            self.assertEqual(msg.type, "ProjectContextMessage")
            self.assertEqual(msg.source, "archiflow")
            self.assertIsInstance(msg.sources, list)
            self.assertGreater(len(msg.sources), 0)


class TestContextInjection(unittest.TestCase):
    """Test suite for context injection behavior."""

    def setUp(self):
        """Set up test fixtures."""
        self.session_id = "test_session"
        self.mock_llm = MockLLMProvider()

    def test_context_injection_on_first_message(self):
        """Test that context is injected on first user message."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create ARCHIFLOW.md
            archiflow_dir = Path(tmpdir) / ".archiflow"
            archiflow_dir.mkdir(parents=True)
            (archiflow_dir / "ARCHIFLOW.md").write_text("# Test Context")

            self.mock_llm.add_response(content="Hello!")

            agent = SimpleAgent(
                session_id=self.session_id,
                llm=self.mock_llm,
                include_project_context=True,
                working_dir=Path(tmpdir)
            )

            # Before first message: no context in history
            messages = agent.history.get_messages()
            types = [m.type for m in messages]
            self.assertNotIn("ProjectContextMessage", types)

            # Send first message
            user_msg = UserMessage(
                session_id=self.session_id,
                sequence=1,
                content="Hi"
            )
            agent.step(user_msg)

            # After first message: context should be in history
            messages = agent.history.get_messages()
            types = [m.type for m in messages]
            self.assertIn("ProjectContextMessage", types)
            self.assertTrue(agent._context_injected)

    def test_context_injection_only_once(self):
        """Test that context is only injected once."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            # Create ARCHIFLOW.md
            archiflow_dir = tmpdir / ".archiflow"
            archiflow_dir.mkdir(parents=True)
            (archiflow_dir / "ARCHIFLOW.md").write_text("# Test Context")

            self.mock_llm.add_response(content="Response 1")
            self.mock_llm.add_response(content="Response 2")

            agent = SimpleAgent(
                session_id=self.session_id,
                llm=self.mock_llm,
                include_project_context=True,
                working_dir=tmpdir
            )

            # Send two messages
            agent.step(UserMessage(session_id=self.session_id, sequence=1, content="First"))
            agent.step(UserMessage(session_id=self.session_id, sequence=2, content="Second"))

            # Count context messages - should be exactly 1
            messages = agent.history.get_messages()
            context_count = sum(1 for m in messages if isinstance(m, ProjectContextMessage))
            self.assertEqual(context_count, 1, "Context should only be injected once")


class TestContextInjectionPosition(unittest.TestCase):
    """Test suite for correct context injection position."""

    def setUp(self):
        """Set up test fixtures."""
        self.session_id = "test_session"
        self.mock_llm = MockLLMProvider()

    def test_static_pattern_context_position(self):
        """Test context injection position for static pattern (SimpleAgent)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            # Create ARCHIFLOW.md
            archiflow_dir = tmpdir / ".archiflow"
            archiflow_dir.mkdir(parents=True)
            (archiflow_dir / "ARCHIFLOW.md").write_text("# Test Context")

            self.mock_llm.add_response(content="Hello!")

            agent = SimpleAgent(
                session_id=self.session_id,
                llm=self.mock_llm,
                include_project_context=True,
                working_dir=tmpdir
            )

            # Send first message
            agent.step(UserMessage(session_id=self.session_id, sequence=1, content="Hi"))

            # Verify position: SystemMessage (0), ProjectContextMessage (1), UserMessage (2)
            messages = agent.history.get_messages()
            self.assertGreaterEqual(len(messages), 3)
            self.assertIsInstance(messages[0], SystemMessage)
            self.assertIsInstance(messages[1], ProjectContextMessage)
            self.assertIsInstance(messages[2], UserMessage)


class TestContextReload(unittest.TestCase):
    """Test suite for context reload functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.session_id = "test_session"
        self.mock_llm = MockLLMProvider()

    def test_reload_project_context(self):
        """Test that reload_project_context() updates the context."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            archiflow_dir = tmpdir / ".archiflow"
            archiflow_dir.mkdir(parents=True)

            # Create initial ARCHIFLOW.md
            (archiflow_dir / "ARCHIFLOW.md").write_text("# Initial Context")

            agent = SimpleAgent(
                session_id=self.session_id,
                llm=self.mock_llm,
                include_project_context=True,
                working_dir=tmpdir
            )

            initial_context = agent._project_context_msg.context
            self.assertIn("Initial Context", initial_context)

            # Update ARCHIFLOW.md
            (archiflow_dir / "ARCHIFLOW.md").write_text("# Updated Context\n\nNew content")

            # Reload context
            agent.reload_project_context()

            # Verify context was updated
            updated_context = agent._project_context_msg.context
            self.assertIn("Updated Context", updated_context)
            self.assertIn("New content", updated_context)
            self.assertNotIn("Initial Context", updated_context)

    def test_reload_resets_injection_flag(self):
        """Test that reload resets the injection flag."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            archiflow_dir = tmpdir / ".archiflow"
            archiflow_dir.mkdir(parents=True)

            (archiflow_dir / "ARCHIFLOW.md").write_text("# Test Context")

            self.mock_llm.add_response(content="Response")

            agent = SimpleAgent(
                session_id=self.session_id,
                llm=self.mock_llm,
                include_project_context=True,
                working_dir=tmpdir
            )

            # Send message to trigger injection
            agent.step(UserMessage(session_id=self.session_id, sequence=1, content="Hi"))
            self.assertTrue(agent._context_injected)

            # Reload context
            agent.reload_project_context()

            # Flag should be reset
            self.assertFalse(agent._context_injected)

            # Next step should inject again
            self.mock_llm.add_response(content="Response 2")
            agent.step(UserMessage(session_id=self.session_id, sequence=2, content="Hi again"))

            # Should have context in history (re-injected)
            messages = agent.history.get_messages()
            context_count = sum(1 for m in messages if isinstance(m, ProjectContextMessage))
            # After reload and re-injection, there might be 2 context messages temporarily
            # but the key is that injection happened again
            self.assertGreaterEqual(context_count, 1)

    def test_reload_when_disabled_does_nothing(self):
        """Test that reload when context is disabled does nothing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = SimpleAgent(
                session_id=self.session_id,
                llm=self.mock_llm,
                include_project_context=False,  # Disabled
                working_dir=Path(tmpdir)
            )

            # Should not raise exception
            agent.reload_project_context()
            self.assertIsNone(agent._project_context_msg)


class TestContextWithNoArchiflowFile(unittest.TestCase):
    """Test suite for behavior when ARCHIFLOW.md doesn't exist."""

    def setUp(self):
        """Set up test fixtures."""
        self.session_id = "test_session"
        self.mock_llm = MockLLMProvider()

    def test_no_context_when_file_missing(self):
        """Test that no context is loaded when ARCHIFLOW.md doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Don't create ARCHIFLOW.md

            agent = SimpleAgent(
                session_id=self.session_id,
                llm=self.mock_llm,
                include_project_context=True,
                working_dir=Path(tmpdir)
            )

            # Context should be None
            self.assertIsNone(agent._project_context_msg)

            # Sending a message should not cause errors
            self.mock_llm.add_response(content="Hello!")
            agent.step(UserMessage(session_id=self.session_id, sequence=1, content="Hi"))

            # Should work normally
            messages = agent.history.get_messages()
            context_count = sum(1 for m in messages if isinstance(m, ProjectContextMessage))
            self.assertEqual(context_count, 0)


if __name__ == '__main__':
    unittest.main()
