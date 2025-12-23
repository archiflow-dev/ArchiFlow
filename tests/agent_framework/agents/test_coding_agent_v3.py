"""Tests for CodingAgentV3."""

import os
import json
import tempfile
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from agent_framework.agents.coding_agent_v3 import CodingAgentV3
from agent_framework.llm.provider import LLMProvider
from agent_framework.llm.model_config import ModelConfig
from agent_framework.messages.types import UserMessage, LLMRespondMessage, ToolCallMessage
from agent_framework.tools.tool_base import ToolRegistry


class TestCodingAgentV3:
    """Test suite for CodingAgentV3."""

    @pytest.fixture
    def mock_llm_provider(self):
        """Create a mock LLM provider for testing."""
        mock_provider = MagicMock()
        mock_response = Mock()
        mock_response.content = "I'm entering IDEATION MODE - Creating specifications..."
        mock_response.tool_calls = []
        mock_provider.generate.return_value = mock_response

        # Add required attributes that BaseAgent expects
        mock_provider.model_config = ModelConfig(
            model_name="test-model",
            context_window=8000,
            max_output_tokens=2000
        )
        mock_provider.get_model_context_size.return_value = 8000
        mock_provider.count_tokens.return_value = 100  # Mock token counting

        return mock_provider

    @pytest.fixture
    def agent(self, mock_llm_provider):
        """Create a CodingAgentV3 instance for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = CodingAgentV3(
                session_id="test_session",
                llm=mock_llm_provider,
                project_directory=tmpdir
            )
            yield agent

    def test_initialization(self, mock_llm_provider):
        """Test agent initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = CodingAgentV3(
                session_id="test_session",
                llm=mock_llm_provider,
                project_directory=tmpdir
            )

            assert agent.session_id == "test_session"
            assert agent.project_directory == tmpdir
            assert (Path(tmpdir) / "src").exists()
            assert (Path(tmpdir) / "tests").exists()
            assert (Path(tmpdir) / "docs").exists()
            assert agent.is_running is True
            # System prompt caching initialized
            assert agent._session_state_hash is None
            assert agent._last_system_prompt is None

    def test_get_system_message_ideation_mode(self, agent):
        """Test system message generation for ideation mode."""
        # No files exist - should be ideation mode
        system_msg = agent.get_system_message()

        assert "CORE_IDENTITY" in system_msg
        assert "MODE_DETECTION" in system_msg
        assert "IDEATION_MODE" in system_msg
        assert "UNIVERSAL_GUIDELINES" in system_msg
        assert "Session ID: test_session" in system_msg

    def test_get_system_message_with_specs(self, agent):
        """Test system message with existing specs."""
        # Create specs.json
        specs_file = Path(agent.project_directory) / "specs.json"
        specs_file.write_text('{"requirements": ["test"]}')

        system_msg = agent.get_system_message()

        assert "IMPLEMENTATION_MODE" in system_msg
        assert "Has Specifications: True" in system_msg

    def test_get_system_message_with_code(self, agent):
        """Test system message with existing code."""
        # Create a source file
        src_file = Path(agent.project_directory) / "src" / "test.py"
        src_file.parent.mkdir(exist_ok=True)
        src_file.write_text("print('hello')")

        system_msg = agent.get_system_message()

        assert "REFACTOR_MODE" in system_msg
        assert "Has Source Code: True" in system_msg

    def test_allowed_tools(self, agent):
        """Test that the agent has the correct tools."""
        tools_schema = agent._get_tools_schema()
        tool_names = [t.get("function", {}).get("name") for t in tools_schema]

        # Check that essential tools are included
        assert "read" in tool_names
        assert "write" in tool_names
        assert "edit" in tool_names
        assert "bash" in tool_names
        assert "web_search" in tool_names

    @patch('agent_framework.agents.coding_agent_v3.CodingAgentV3._update_memory')
    def test_step_with_user_message(self, mock_update_memory, agent, mock_llm_provider):
        """Test processing a user message."""
        message = UserMessage(
            session_id="test_session",
            sequence=0,
            content="Create a REST API"
        )

        response = agent.step(message)

        assert isinstance(response, ToolCallMessage)
        assert response.tool_calls is not None
        mock_llm_provider.generate.assert_called_once()
        mock_update_memory.assert_called()

    @patch('agent_framework.agents.coding_agent_v3.CodingAgentV3._update_memory')
    def test_step_rebuilds_system_prompt_with_caching(self, mock_update_memory, agent, mock_llm_provider):
        """Test that system prompt is rebuilt each step but cached when state unchanged."""
        # System prompt should be None initially
        assert agent._session_state_hash is None
        assert agent._last_system_prompt is None

        message = UserMessage(
            session_id="test_session",
            sequence=0,
            content="Test"
        )

        # First step should build and cache system prompt
        agent.step(message)

        # After first step, system prompt should be cached
        assert agent._session_state_hash is not None
        assert agent._last_system_prompt is not None
        first_hash = agent._session_state_hash
        first_prompt = agent._last_system_prompt

        # Second step with unchanged state should use cached prompt
        message2 = UserMessage(
            session_id="test_session",
            sequence=1,
            content="Another test"
        )
        agent.step(message2)

        # Hash and prompt should be the same (cached)
        assert agent._session_state_hash == first_hash
        assert agent._last_system_prompt == first_prompt

        # Note: System message is NOT stored in history (only prepended to LLM call)
        # So history should not contain system messages
        system_msgs = [msg for msg in agent.history.get_messages()
                      if hasattr(msg, '__class__') and msg.__class__.__name__ == 'SystemMessage']
        assert len(system_msgs) == 0

    def test_sequence_counter(self, agent, mock_llm_provider):
        """Test that sequence counter increments correctly."""
        seq1 = agent._next_sequence()
        seq2 = agent._next_sequence()
        seq3 = agent._next_sequence()

        assert seq1 == 0
        assert seq2 == 1
        assert seq3 == 2

    def test_format_finish_message(self, agent):
        """Test finish message formatting."""
        reason = "Task completed successfully"
        result = "Created 3 files and 2 tests"

        formatted = agent._format_finish_message(reason, result)

        assert reason in formatted
        assert result in formatted

    def test_mode_detection_keywords(self, agent):
        """Test that mode detection checks for keywords."""
        system_msg = agent.get_system_message()

        # Check that debug keywords are included
        assert "debug" in system_msg.lower()
        assert "fix error" in system_msg.lower()
        assert "refactor" in system_msg.lower()
        assert "review" in system_msg.lower()
        assert "test" in system_msg.lower()

    def test_workflow_artifacts(self, agent):
        """Test that all workflow artifacts are mentioned."""
        system_msg = agent.get_system_message()

        # Check that all artifact files are mentioned
        artifacts = [
            "specs.json",
            "debug_report.json",
            "refactor_plan.json",
            "feature_plan.json",
            "code_review.json",
            "test_plan.json",
            "implementation_plan.json"
        ]

        for artifact in artifacts:
            assert artifact in system_msg

    @patch('agent_framework.agents.coding_agent_v3.CodingAgentV3._update_memory')
    def test_mode_announcement(self, mock_update_memory, agent, mock_llm_provider):
        """Test that the agent announces its mode."""
        # Mock response with mode announcement
        mock_response = Mock()
        mock_response.content = "I'm entering IDEATION MODE - Creating specifications..."
        mock_response.tool_calls = [Mock()]
        mock_llm_provider.generate.return_value = mock_response

        message = UserMessage(
            session_id="test_session",
            sequence=0,
            content="Create something new"
        )

        agent.step(message)

        # The system prompt should include mode announcements
        system_msg = agent.get_system_message()
        assert "I'm entering" in system_msg
        assert "MODE" in system_msg

    def test_save_then_wait_rule(self, agent):
        """Test that save-then-wait rule is in universal guidelines."""
        system_msg = agent.get_system_message()

        # Check for critical save-then-wait instructions
        assert "Save-Then-Wait Rule" in system_msg
        assert "STOP AND WAIT" in system_msg
        assert "Do not proceed without explicit approval" in system_msg

    def test_code_quality_guidelines(self, agent):
        """Test that code quality guidelines are included."""
        system_msg = agent.get_system_message()

        quality_keywords = [
            "clean",
            "readable",
            "maintainable",
            "documentation",
            "best practices",
            "error handling"
        ]

        for keyword in quality_keywords:
            assert keyword in system_msg.lower()

    def test_tool_usage_guidelines(self, agent):
        """Test that tool usage guidelines are included."""
        system_msg = agent.get_system_message()

        # Check for tool usage patterns
        assert "TOOL USAGE" in system_msg
        assert "Available Tools" in system_msg
        assert "read_tool" in system_msg
        assert "write_tool" in system_msg

    @patch('agent_framework.agents.coding_agent_v3.CodingAgentV3._update_memory')
    def test_workflow_phases(self, mock_update_memory, agent, mock_llm_provider):
        """Test that workflow phases are properly structured."""
        system_msg = agent.get_system_message()

        # Check for phase structure in modes
        assert "Phase 1" in system_msg
        assert "Phase 2" in system_msg
        assert "Exit condition" in system_msg

    @pytest.mark.parametrize("mode", [
        "ideation", "implementation", "debug",
        "refactor", "feature", "review", "test"
    ])
    def test_all_modes_documented(self, mode, agent):
        """Test that all modes are documented in system prompt."""
        system_msg = agent.get_system_message()
        mode_upper = mode.upper()

        # Check for mode definition
        assert f"{mode_upper} MODE" in system_msg
        assert f"ENTER {mode_upper} MODE" in system_msg

    def test_completion_criteria(self, agent):
        """Test that completion criteria are defined."""
        system_msg = agent.get_system_message()

        assert "COMPLETION_CRITERIA" in system_msg
        assert "finish_task" in system_msg
        assert "[SUCCESS]" in system_msg