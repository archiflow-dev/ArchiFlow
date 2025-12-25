"""
End-to-end integration tests for the hierarchy system.

Tests the complete configuration flow:
1. Framework defaults
2. Global user config (~/.archiflow/)
3. Project config (.archiflow/)
4. Local project config (.archiflow/*.local.*)
5. Environment variable overrides
6. ARCHIFLOW.md context loading
7. Agent integration
"""
import json
import os
import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

from agent_framework.config.hierarchy import ConfigHierarchy
from agent_framework.agents.coding_agent import CodingAgent
from agent_framework.agents.research_agent import ResearchAgent
from agent_framework.agents.coding_agent_v3 import CodingAgentV3
from agent_framework.llm.provider import LLMProvider, LLMResponse, FinishReason
from agent_framework.messages.types import UserMessage, ProjectContextMessage


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


class TestHierarchyE2E(unittest.TestCase):
    """End-to-end tests for the hierarchy system."""

    def test_complete_settings_hierarchy(self):
        """Test complete settings.json hierarchy flow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            archiflow_dir = project_dir / ".archiflow"
            archiflow_dir.mkdir()

            # Create project config
            project_config = {
                "agent": {
                    "defaultModel": "project-model",
                    "maxIterations": 15
                },
                "autoRefinement": {
                    "enabled": True,
                    "threshold": 8.0,
                    "minLength": 10
                }
            }
            (archiflow_dir / "settings.json").write_text(json.dumps(project_config))

            # Create local config
            local_config = {
                "agent": {
                    "timeout": 500000
                }
            }
            (archiflow_dir / "settings.local.json").write_text(json.dumps(local_config))

            # Load hierarchy
            hierarchy = ConfigHierarchy(working_dir=project_dir)
            snapshot = hierarchy.load()
            settings = snapshot.settings

            # Verify merge: project + local
            self.assertEqual(settings["agent"]["defaultModel"], "project-model")
            self.assertEqual(settings["agent"]["maxIterations"], 15)
            self.assertEqual(settings["agent"]["timeout"], 500000)
            self.assertTrue(settings["autoRefinement"]["enabled"])
            # From project config
            self.assertEqual(settings["autoRefinement"]["threshold"], 8.0)
            self.assertEqual(settings["autoRefinement"]["minLength"], 10)

    def test_complete_context_hierarchy(self):
        """Test complete ARCHIFLOW.md context loading flow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            archiflow_dir = project_dir / ".archiflow"
            archiflow_dir.mkdir()

            # Create project ARCHIFLOW.md
            project_context = """# Project Configuration

## Tech Stack
- Backend: Python 3.10, FastAPI
- Frontend: React 18, TypeScript

## Coding Standards
- Follow PEP 8
- Max function length: 50 lines
"""
            (archiflow_dir / "ARCHIFLOW.md").write_text(project_context)

            # Create local ARCHIFLOW.md
            local_context = """# Local Overrides

## My Preferences
- Use 4 spaces for indentation
- Add docstrings to all functions
"""
            (archiflow_dir / "ARCHIFLOW.local.md").write_text(local_context)

            # Load hierarchy
            hierarchy = ConfigHierarchy(working_dir=project_dir)
            snapshot = hierarchy.load()
            context = snapshot.context

            # Verify both contexts are loaded
            self.assertIn("Project Configuration", context)
            self.assertIn("Tech Stack", context)
            self.assertIn("Local Overrides", context)
            self.assertIn("4 spaces", context)
            self.assertIn("PEP 8", context)

    def test_env_var_override(self):
        """Test environment variable override in hierarchy."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            archiflow_dir = project_dir / ".archiflow"
            archiflow_dir.mkdir()

            # Create config with autoRefinement disabled
            config = {"autoRefinement": {"enabled": False, "threshold": 7.0}}
            (archiflow_dir / "settings.json").write_text(json.dumps(config))

            # Set environment variable
            os.environ["AUTO_REFINE_PROMPTS"] = "true"
            os.environ["AUTO_REFINE_THRESHOLD"] = "9.0"

            try:
                hierarchy = ConfigHierarchy(working_dir=project_dir)
                snapshot = hierarchy.load()
                settings = snapshot.settings

                # Note: Environment variables are NOT applied by ConfigHierarchy.load()
                # They are applied at the point of use (e.g., in PromptPreprocessor)
                # So this test verifies the base settings
                self.assertFalse(settings["autoRefinement"]["enabled"])
                self.assertEqual(settings["autoRefinement"]["threshold"], 7.0)
            finally:
                # Cleanup
                del os.environ["AUTO_REFINE_PROMPTS"]
                del os.environ["AUTO_REFINE_THRESHOLD"]

    def test_coding_agent_with_hierarchy_context(self):
        """Test CodingAgent loads context from hierarchy."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            archiflow_dir = project_dir / ".archiflow"
            archiflow_dir.mkdir()

            # Create ARCHIFLOW.md
            context = """# Project Context

## Coding Standards
- Use type hints
- Follow PEP 8
- Write docstrings
"""
            (archiflow_dir / "ARCHIFLOW.md").write_text(context)

            # Create agent with project context enabled
            mock_llm = MockLLMProvider()
            mock_llm.add_response(content="Hello!")

            agent = CodingAgent(
                session_id="test_session",
                llm=mock_llm,
                project_directory=str(project_dir)
            )

            # Verify context is loaded
            self.assertIsNotNone(agent._project_context_msg)
            self.assertIsInstance(agent._project_context_msg, ProjectContextMessage)
            self.assertIn("Coding Standards", agent._project_context_msg.context)

            # Verify context appears in history after first step
            agent.step(UserMessage(session_id="test_session", sequence=0, content="Hi"))
            messages = agent.history.get_messages()
            context_messages = [m for m in messages if isinstance(m, ProjectContextMessage)]
            self.assertEqual(len(context_messages), 1)

    def test_research_agent_with_hierarchy_context(self):
        """Test ResearchAgent loads context from hierarchy."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            archiflow_dir = project_dir / ".archiflow"
            archiflow_dir.mkdir()

            # Create ARCHIFLOW.md
            context = """# Research Context

## Research Guidelines
- Use authoritative sources
- Cite references
- Verify claims
"""
            (archiflow_dir / "ARCHIFLOW.md").write_text(context)

            # Create agent
            mock_llm = MockLLMProvider()
            mock_llm.add_response(content="Researching...")

            agent = ResearchAgent(
                session_id="test_session",
                llm=mock_llm,
                project_directory=str(project_dir)
            )

            # Verify context is loaded
            self.assertIsNotNone(agent._project_context_msg)
            self.assertIn("Research Guidelines", agent._project_context_msg.context)

    def test_coding_agent_v3_with_hierarchy_context(self):
        """Test CodingAgentV3 loads context from hierarchy."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            archiflow_dir = project_dir / ".archiflow"
            archiflow_dir.mkdir()

            # Create ARCHIFLOW.md
            context = """# V3 Coding Context

## Modern Python
- Use dataclasses for data
- Use async/await
- Type hints required
"""
            (archiflow_dir / "ARCHIFLOW.md").write_text(context)

            # Create agent
            mock_llm = MockLLMProvider()
            mock_llm.add_response(content="Coding...")

            agent = CodingAgentV3(
                session_id="test_session",
                llm=mock_llm,
                project_directory=str(project_dir)
            )

            # Verify context is loaded
            self.assertIsNotNone(agent._project_context_msg)
            self.assertIn("Modern Python", agent._project_context_msg.context)

    def test_hierarchy_invalidation(self):
        """Test cache invalidation in hierarchy."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            archiflow_dir = project_dir / ".archiflow"
            archiflow_dir.mkdir()

            # Create initial config
            config = {"agent": {"maxIterations": 10}}
            (archiflow_dir / "settings.json").write_text(json.dumps(config))

            hierarchy = ConfigHierarchy(working_dir=project_dir)
            snapshot1 = hierarchy.load()
            settings1 = snapshot1.settings
            self.assertEqual(settings1["agent"]["maxIterations"], 10)

            # Update config file
            config = {"agent": {"maxIterations": 20}}
            (archiflow_dir / "settings.json").write_text(json.dumps(config))

            # Without force_reload, should get cached value (if files haven't changed recently)
            # But since we just wrote the file, mtime will be different
            snapshot2 = hierarchy.load(force_reload=False)
            settings2 = snapshot2.settings
            # With file change detection, should get new value
            self.assertEqual(settings2["agent"]["maxIterations"], 20)  # Detected change

            # With force_reload, should always get new value
            snapshot3 = hierarchy.load(force_reload=True)
            settings3 = snapshot3.settings
            self.assertEqual(settings3["agent"]["maxIterations"], 20)  # Reloaded

    def test_missing_archiflow_directory(self):
        """Test hierarchy behavior when .archiflow doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            # Don't create .archiflow directory

            hierarchy = ConfigHierarchy(working_dir=project_dir)
            snapshot = hierarchy.load()
            settings = snapshot.settings
            context = snapshot.context

            # Should return empty settings (framework defaults are in agents, not hierarchy)
            self.assertIsNotNone(settings)
            self.assertEqual(settings, {})

            # Context should be empty
            self.assertEqual(context, "")

    def test_source_metadata_in_context(self):
        """Test that context includes source file metadata."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            archiflow_dir = project_dir / ".archiflow"
            archiflow_dir.mkdir()

            # Create ARCHIFLOW.md
            context = "# Test Context"
            (archiflow_dir / "ARCHIFLOW.md").write_text(context)

            # Create agent to load context
            mock_llm = MockLLMProvider()
            agent = CodingAgent(
                session_id="test_session",
                llm=mock_llm,
                project_directory=str(project_dir)
            )

            # Verify sources metadata
            self.assertIsNotNone(agent._project_context_msg.sources)
            self.assertGreater(len(agent._project_context_msg.sources), 0)
            # Should include the path to ARCHIFLOW.md
            self.assertTrue(any("ARCHIFLOW.md" in s for s in agent._project_context_msg.sources))


class TestHierarchyPrecedence(unittest.TestCase):
    """Tests for configuration precedence order."""

    def test_precedence_order_local_highest(self):
        """Test that local config has highest priority."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            archiflow_dir = project_dir / ".archiflow"
            archiflow_dir.mkdir()

            # Framework default: maxIterations = 10
            # Project config: maxIterations = 15
            # Local config: maxIterations = 20
            (archiflow_dir / "settings.json").write_text(
                json.dumps({"agent": {"maxIterations": 15}})
            )
            (archiflow_dir / "settings.local.json").write_text(
                json.dumps({"agent": {"maxIterations": 20}})
            )

            hierarchy = ConfigHierarchy(working_dir=project_dir)
            snapshot = hierarchy.load()
            settings = snapshot.settings

            self.assertEqual(settings["agent"]["maxIterations"], 20)

    def test_precedence_nested_merge(self):
        """Test that nested values are merged correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            archiflow_dir = project_dir / ".archiflow"
            archiflow_dir.mkdir()

            # Project config has full autoRefinement config
            # Local config overrides only "enabled"
            (archiflow_dir / "settings.json").write_text(
                json.dumps({"autoRefinement": {"enabled": False, "threshold": 8.0, "minLength": 10}})
            )
            (archiflow_dir / "settings.local.json").write_text(
                json.dumps({"autoRefinement": {"enabled": True}})
            )

            hierarchy = ConfigHierarchy(working_dir=project_dir)
            snapshot = hierarchy.load()
            settings = snapshot.settings

            # Enabled should be overridden (from local)
            self.assertTrue(settings["autoRefinement"]["enabled"])
            # Threshold should be preserved from project
            self.assertEqual(settings["autoRefinement"]["threshold"], 8.0)
            # MinLength should be preserved from project
            self.assertEqual(settings["autoRefinement"]["minLength"], 10)


if __name__ == '__main__':
    unittest.main()
