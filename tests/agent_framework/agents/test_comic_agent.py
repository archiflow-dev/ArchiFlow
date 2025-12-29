"""
Tests for ComicAgent.

Comprehensive test coverage for comic book creation agent.
"""

import unittest
import tempfile
import shutil
import os
import json
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

from agent_framework.agents.comic_agent import ComicAgent
from agent_framework.llm.provider import LLMProvider, LLMResponse, FinishReason
from agent_framework.messages.types import UserMessage, SystemMessage, LLMRespondMessage
from agent_framework.tools.tool_base import ToolRegistry


class MockLLMProvider(LLMProvider):
    """Mock LLM provider for testing."""

    def __init__(self, response_content="Test response", **kwargs):
        """Initialize mock provider."""
        self.response_content = response_content
        self.call_count = 0
        self.last_messages = None
        self.last_tools = None
        # Call parent with minimal required args
        super().__init__(model="mock-model", usage_tracker=None)

    def generate(self, messages, tools=None, **kwargs):
        """Mock generate method."""
        self.call_count += 1
        self.last_messages = messages
        self.last_tools = tools

        return LLMResponse(
            content=self.response_content,
            finish_reason=FinishReason.STOP,
            tool_calls=None
        )

    def stream(self, messages, tools=None, **kwargs):
        """Mock stream method - not used in tests."""
        raise NotImplementedError("Streaming not implemented in mock")


class TestComicAgent(unittest.TestCase):
    """Test suite for ComicAgent."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.session_id = "test_session"
        self.mock_llm = MockLLMProvider()
        self.google_api_key = "fake_api_key"

        # Create agent
        self.agent = ComicAgent(
            session_id=self.session_id,
            llm=self.mock_llm,
            google_api_key=self.google_api_key,
            project_directory=self.temp_dir
        )

    def tearDown(self):
        """Clean up test files."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    # ===== Initialization Tests =====

    def test_initialization(self):
        """Test agent initialization."""
        self.assertIsNotNone(self.agent)
        self.assertEqual(self.agent.session_id, self.session_id)
        self.assertIsNotNone(self.agent.llm)
        self.assertTrue(self.agent.is_running)
        self.assertEqual(self.agent.sequence_counter, 0)

    def test_initialization_creates_directories(self):
        """Test that initialization creates required directories."""
        session_path = Path(self.agent.project_directory)

        # Check main directory exists
        self.assertTrue(session_path.exists())

        # Check subdirectories exist
        self.assertTrue((session_path / "character_refs").exists())
        self.assertTrue((session_path / "panels").exists())
        self.assertTrue((session_path / "pages").exists())

    def test_initialization_sets_execution_context(self):
        """Test that execution context is properly set."""
        self.assertIsNotNone(self.agent.execution_context)
        self.assertEqual(self.agent.execution_context.session_id, self.session_id)
        # Working directory should match project_directory (may be temp dir in tests)
        self.assertIn(self.temp_dir, self.agent.execution_context.working_directory)

    def test_agent_configuration(self):
        """Test agent configuration constants."""
        self.assertEqual(self.agent.DEFAULT_PAGE_COUNT, 6)
        self.assertEqual(self.agent.DEFAULT_PANELS_PER_PAGE, 6)
        self.assertEqual(self.agent.SCRIPT_FILE, "script.md")
        self.assertEqual(self.agent.SPEC_FILE, "comic_spec.md")
        self.assertIn("generate_comic_panel", self.agent.ALLOWED_TOOLS)

    # ===== System Message Tests =====

    def test_get_system_message_script_mode(self):
        """Test system message generation in script mode (no files)."""
        system_msg = self.agent.get_system_message()

        # Should contain core identity
        self.assertIn("Comic Book Creator", system_msg)
        self.assertIn("Visual Storyteller", system_msg)

        # Should contain mode detection
        self.assertIn("MODE DETECTION", system_msg)

        # Should contain script mode instructions
        self.assertIn("SCRIPT MODE", system_msg)
        self.assertIn("script.md", system_msg)

        # Should contain universal guidelines
        self.assertIn("UNIVERSAL GUIDELINES", system_msg)

        # Should NOT contain spec mode (no script exists)
        # (Actually it contains all modes, but script mode should be primary)

    def test_get_system_message_spec_mode(self):
        """Test system message generation in spec mode (script exists)."""
        # Create script.md
        session_path = Path(self.agent.project_directory)
        (session_path / "script.md").write_text("# Test Script")

        system_msg = self.agent.get_system_message()

        # Should contain spec mode instructions
        self.assertIn("SPEC MODE", system_msg)
        self.assertIn("comic_spec.md", system_msg)

        # Check session context
        self.assertIn("Has Script: True", system_msg)
        self.assertIn("Has Spec: False", system_msg)

    def test_get_system_message_generation_mode(self):
        """Test system message generation in generation mode (spec exists)."""
        # Create script.md and comic_spec.md
        session_path = Path(self.agent.project_directory)
        (session_path / "script.md").write_text("# Test Script")
        (session_path / "comic_spec.md").write_text("# Test Spec")

        system_msg = self.agent.get_system_message()

        # Should contain generation mode instructions
        self.assertIn("GENERATION MODE", system_msg)
        self.assertIn("Character References", system_msg)

        # Check session context
        self.assertIn("Has Script: True", system_msg)
        self.assertIn("Has Spec: True", system_msg)
        self.assertIn("Has Panels: False", system_msg)

    def test_get_system_message_export_mode(self):
        """Test system message generation in export mode (panels exist)."""
        # Create all necessary files and panels
        session_path = Path(self.agent.project_directory)
        (session_path / "script.md").write_text("# Test Script")
        (session_path / "comic_spec.md").write_text("# Test Spec")

        # Create a panel file
        panels_dir = session_path / "panels"
        (panels_dir / "page_01_panel_01.png").write_bytes(b"fake image data")

        system_msg = self.agent.get_system_message()

        # Should contain export mode instructions
        self.assertIn("EXPORT MODE", system_msg)

        # Check session context
        self.assertIn("Has Panels: True", system_msg)

    def test_system_message_includes_session_directory(self):
        """Test that system message includes session directory path."""
        system_msg = self.agent.get_system_message()
        self.assertIn(self.agent.project_directory, system_msg)

    # ===== Tool Schema Tests =====

    def test_get_tools_schema(self):
        """Test getting tool schema."""
        schema = self.agent._get_tools_schema()

        self.assertIsInstance(schema, list)
        self.assertGreater(len(schema), 0)

        # Check that only allowed tools are included
        tool_names = [tool['function']['name'] for tool in schema]
        for name in tool_names:
            self.assertIn(name, self.agent.ALLOWED_TOOLS)

    def test_tools_schema_includes_generate_comic_panel(self):
        """Test that generate_comic_panel is in tools schema."""
        schema = self.agent._get_tools_schema()
        tool_names = [tool['function']['name'] for tool in schema]
        self.assertIn("generate_comic_panel", tool_names)

    # ===== Step Method Tests =====

    def test_step_adds_system_message_on_first_call(self):
        """Test that step adds system message on first call."""
        user_msg = UserMessage(
            session_id=self.session_id,
            sequence=0,
            content="Create a comic about a robot"
        )

        # Initial history should be empty
        self.assertEqual(len(self.agent.history.get_messages()), 0)

        # Call step
        response = self.agent.step(user_msg)

        # System message should be added
        self.assertTrue(self.agent._system_added)
        messages = self.agent.history.get_messages()

        # Should have: user message, system message, and potentially response
        self.assertGreater(len(messages), 1)

        # First or second message should be system message
        has_system = any(isinstance(msg, SystemMessage) for msg in messages)
        self.assertTrue(has_system)

    def test_step_returns_llm_response(self):
        """Test that step returns LLM response."""
        user_msg = UserMessage(
            session_id=self.session_id,
            sequence=0,
            content="Create a comic about a robot"
        )

        response = self.agent.step(user_msg)

        self.assertIsNotNone(response)
        self.assertIsInstance(response, LLMRespondMessage)
        self.assertEqual(response.content, "Test response")

    def test_step_calls_llm_with_tools(self):
        """Test that step calls LLM with tools."""
        user_msg = UserMessage(
            session_id=self.session_id,
            sequence=0,
            content="Create a comic"
        )

        self.agent.step(user_msg)

        # LLM should have been called
        self.assertEqual(self.mock_llm.call_count, 1)

        # Tools should have been passed
        self.assertIsNotNone(self.mock_llm.last_tools)
        self.assertGreater(len(self.mock_llm.last_tools), 0)

    def test_step_updates_memory(self):
        """Test that step updates memory."""
        user_msg = UserMessage(
            session_id=self.session_id,
            sequence=0,
            content="Create a comic"
        )

        initial_count = len(self.agent.history.get_messages())

        self.agent.step(user_msg)

        final_count = len(self.agent.history.get_messages())

        # Memory should have grown
        self.assertGreater(final_count, initial_count)

    def test_step_increments_sequence_counter(self):
        """Test that step increments sequence counter."""
        user_msg = UserMessage(
            session_id=self.session_id,
            sequence=0,
            content="Create a comic"
        )

        initial_seq = self.agent.sequence_counter

        self.agent.step(user_msg)

        # Sequence should have incremented
        self.assertGreater(self.agent.sequence_counter, initial_seq)

    # ===== Memory Update Tests =====

    def test_update_memory_adds_user_message(self):
        """Test that update_memory adds user message to history."""
        user_msg = UserMessage(
            session_id=self.session_id,
            sequence=0,
            content="Test message"
        )

        initial_count = len(self.agent.history.get_messages())

        self.agent._update_memory(user_msg)

        final_count = len(self.agent.history.get_messages())

        self.assertEqual(final_count, initial_count + 1)

    def test_next_sequence_increments(self):
        """Test that _next_sequence increments correctly."""
        seq1 = self.agent._next_sequence()
        seq2 = self.agent._next_sequence()
        seq3 = self.agent._next_sequence()

        self.assertEqual(seq1, 0)
        self.assertEqual(seq2, 1)
        self.assertEqual(seq3, 2)

    # ===== Setup Tools Tests =====

    def test_setup_tools_configures_image_provider(self):
        """Test that _setup_tools configures image provider."""
        # This test checks that the setup was called during init
        # We can verify by checking if the tool exists
        tool = self.agent.tools.get("generate_comic_panel")
        self.assertIsNotNone(tool)

        # Note: Actual image provider configuration requires Google API key
        # which we're mocking, so we just verify the tool exists

    # ===== Integration Tests =====

    def test_full_workflow_script_mode(self):
        """Test full workflow in script mode."""
        # User sends initial message
        user_msg = UserMessage(
            session_id=self.session_id,
            sequence=0,
            content="Create a comic about a brave robot"
        )

        # Agent processes message
        response = self.agent.step(user_msg)

        # Should get a response
        self.assertIsNotNone(response)
        self.assertIsInstance(response, LLMRespondMessage)

        # System message should be added
        self.assertTrue(self.agent._system_added)

        # History should contain messages
        messages = self.agent.history.get_messages()
        self.assertGreater(len(messages), 0)

    def test_multiple_steps(self):
        """Test multiple step calls."""
        messages = [
            UserMessage(session_id=self.session_id, sequence=i, content=f"Message {i}")
            for i in range(3)
        ]

        for msg in messages:
            response = self.agent.step(msg)
            self.assertIsNotNone(response)

        # Should have processed all messages
        self.assertEqual(self.mock_llm.call_count, 3)

        # History should contain all messages
        history = self.agent.history.get_messages()
        self.assertGreater(len(history), 3)

    # ===== File Handling Tests =====

    def test_agent_with_existing_script(self):
        """Test agent behavior when script already exists."""
        # Create script.md before initializing agent
        session_path = Path(f"data/sessions/{self.session_id}")
        session_path.mkdir(parents=True, exist_ok=True)
        (session_path / "script.md").write_text("# Existing Script")

        # Create new agent
        agent = ComicAgent(
            session_id=self.session_id,
            llm=self.mock_llm,
            google_api_key=self.google_api_key
        )

        # System message should reflect script exists
        system_msg = agent.get_system_message()
        self.assertIn("Has Script: True", system_msg)

        # Clean up
        if session_path.exists():
            shutil.rmtree(session_path)

    def test_agent_with_existing_spec(self):
        """Test agent behavior when spec already exists."""
        # Create both script and spec
        session_path = Path(f"data/sessions/{self.session_id}")
        session_path.mkdir(parents=True, exist_ok=True)
        (session_path / "script.md").write_text("# Existing Script")
        (session_path / "comic_spec.md").write_text("# Existing Spec")

        # Create new agent
        agent = ComicAgent(
            session_id=self.session_id,
            llm=self.mock_llm,
            google_api_key=self.google_api_key
        )

        # System message should reflect both exist
        system_msg = agent.get_system_message()
        self.assertIn("Has Script: True", system_msg)
        self.assertIn("Has Spec: True", system_msg)

        # Clean up
        if session_path.exists():
            shutil.rmtree(session_path)

    # ===== Constants and Configuration Tests =====

    def test_allowed_tools_list(self):
        """Test that ALLOWED_TOOLS contains expected tools."""
        expected_tools = [
            "read", "write", "list", "bash",
            "web_search", "web_fetch",
            "generate_comic_panel", "finish_task"
        ]

        for tool in expected_tools:
            self.assertIn(tool, self.agent.ALLOWED_TOOLS)

    def test_file_name_constants(self):
        """Test file name constants."""
        self.assertEqual(self.agent.SCRIPT_FILE, "script.md")
        self.assertEqual(self.agent.SPEC_FILE, "comic_spec.md")
        self.assertEqual(self.agent.PANEL_MAP_FILE, "panel_map.json")
        self.assertEqual(self.agent.METADATA_FILE, "metadata.json")

    def test_directory_constants(self):
        """Test directory name constants."""
        self.assertEqual(self.agent.CHARACTER_REFS_DIR, "character_refs")
        self.assertEqual(self.agent.PANELS_DIR, "panels")
        self.assertEqual(self.agent.PAGES_DIR, "pages")

    # ===== Error Handling Tests =====

    def test_step_when_not_running(self):
        """Test step behavior when agent is not running."""
        self.agent.is_running = False

        user_msg = UserMessage(
            session_id=self.session_id,
            sequence=0,
            content="Test"
        )

        response = self.agent.step(user_msg)

        # Should return None when not running
        self.assertIsNone(response)

    # ===== Prompt Content Tests =====

    def test_core_identity_in_system_message(self):
        """Test that core identity is in system message."""
        system_msg = self.agent.get_system_message()

        # Check for key phrases from CORE_IDENTITY
        self.assertIn("Comic Book Creator", system_msg)
        self.assertIn("Visual Storyteller", system_msg)
        self.assertIn("session directory", system_msg.lower())

    def test_mode_detection_in_system_message(self):
        """Test that mode detection is in system message."""
        system_msg = self.agent.get_system_message()

        # Check for mode detection section
        self.assertIn("MODE DETECTION", system_msg)
        self.assertIn("SCRIPT MODE", system_msg)
        self.assertIn("SPEC MODE", system_msg)
        self.assertIn("GENERATION MODE", system_msg)

    def test_tool_guidelines_in_system_message(self):
        """Test that tool guidelines are in system message."""
        system_msg = self.agent.get_system_message()

        # Check for tool usage guidelines
        self.assertIn("TOOL USAGE", system_msg)
        self.assertIn("generate_comic_panel", system_msg)

    def test_save_then_wait_rule_in_system_message(self):
        """Test that save-then-wait rule is emphasized."""
        system_msg = self.agent.get_system_message()

        # Check for critical save-then-wait instructions
        self.assertIn("STOP AND WAIT", system_msg)
        self.assertIn("Save-Then-Wait", system_msg)


if __name__ == '__main__':
    unittest.main()
