"""
Unit tests for ProductManagerAgent.

These tests verify the core functionality of the product manager agent,
including initialization, tool filtering, and message processing.
"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, MagicMock

from agent_framework.agents.product_manager_agent import ProductManagerAgent
from agent_framework.llm.mock import MockLLMProvider
from agent_framework.llm.provider import LLMResponse
from agent_framework.messages.types import (
    UserMessage, ToolResultObservation, AgentFinishedMessage,
    ToolCallMessage, LLMRespondMessage
)


@pytest.fixture
def mock_llm():
    """Create a mock LLM provider."""
    return MockLLMProvider()


@pytest.fixture
def test_project_dir(tmp_path):
    """Create a temporary project directory with sample files."""
    # Create directory structure
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()

    src_dir = tmp_path / "src"
    src_dir.mkdir()

    # Create sample files
    (tmp_path / "README.md").write_text("# Test Project\n")
    (docs_dir / "notes.md").write_text("# Notes\n")

    return tmp_path


@pytest.fixture
def test_agent(mock_llm, test_project_dir):
    """Create a test agent instance."""
    return ProductManagerAgent(
        session_id="test_session",
        llm=mock_llm,
        project_directory=str(test_project_dir)
    )


class TestAgentInitialization:
    """Test agent initialization and setup."""

    def test_agent_creation(self, test_agent, test_project_dir):
        """Test that agent can be created successfully."""
        assert test_agent.session_id == "test_session"
        assert test_agent.project_directory == test_project_dir
        assert test_agent.is_running is True

    def test_project_directory_validation(self, mock_llm):
        """Test that invalid project directory raises error."""
        with pytest.raises(ValueError, match="does not exist"):
            ProductManagerAgent(
                session_id="test",
                llm=mock_llm,
                project_directory="/nonexistent/path"
            )

    def test_project_directory_not_dir(self, mock_llm, tmp_path):
        """Test that file path instead of directory raises error."""
        file_path = tmp_path / "file.txt"
        file_path.write_text("test")

        with pytest.raises(ValueError, match="not a directory"):
            ProductManagerAgent(
                session_id="test",
                llm=mock_llm,
                project_directory=str(file_path)
            )

    def test_default_project_directory(self, mock_llm):
        """Test that agent uses cwd if no directory specified."""
        agent = ProductManagerAgent(
            session_id="test",
            llm=mock_llm
        )
        assert agent.project_directory == Path.cwd()

    def test_execution_context_created(self, test_agent, test_project_dir):
        """Test that execution context is properly initialized."""
        assert test_agent.execution_context is not None
        assert test_agent.execution_context.session_id == "test_session"
        assert test_agent.execution_context.working_directory == str(test_project_dir)

    def test_system_prompt_template(self, test_agent):
        """Test that system prompt template contains required elements."""
        # ProjectAgent stores system prompt as template, not in history initially
        assert hasattr(test_agent, '_system_prompt_template')
        assert test_agent._system_prompt_template is not None

        # Verify template contains placeholder for project directory
        assert "{project_directory}" in test_agent._system_prompt_template
        assert "Product Manager Agent" in test_agent._system_prompt_template
        assert "DISCOVERY" in test_agent._system_prompt_template
        assert "finish_task" in test_agent._system_prompt_template


class TestToolFiltering:
    """Test that only documentation tools are exposed."""

    def test_allowed_tools_registered(self, test_agent):
        """Test that all required documentation tools are available."""
        required_tools = ["todo_write", "todo_read", "write", "read", "list", "glob", "finish_task"]

        for tool_name in required_tools:
            tool = test_agent.tools.get(tool_name)
            assert tool is not None, f"Tool {tool_name} should be available"

    def test_forbidden_tools_in_global_registry(self, test_agent):
        """Test that code modification tools exist in global registry but..."""
        # They exist in the singleton registry
        assert test_agent.tools.get("edit") is not None
        assert test_agent.tools.get("bash") is not None
        assert test_agent.tools.get("grep") is not None

    def test_forbidden_tools_not_in_llm_schema(self, test_agent):
        """Test that code modification tools are NOT exposed to LLM."""
        schema = test_agent._get_tools_schema()
        schema_tool_names = [tool['function']['name'] for tool in schema]

        # Verify forbidden tools are NOT in schema
        assert "edit" not in schema_tool_names
        assert "bash" not in schema_tool_names
        assert "grep" not in schema_tool_names
        assert "multi_edit" not in schema_tool_names

    def test_only_allowed_tools_in_schema(self, test_agent):
        """Test that LLM schema contains exactly the allowed tools."""
        schema = test_agent._get_tools_schema()
        schema_tool_names = set([tool['function']['name'] for tool in schema])

        expected_tools = set(test_agent.allowed_tools)
        assert schema_tool_names == expected_tools

    def test_allowed_tools_list(self, test_agent):
        """Test that allowed_tools list is correct."""
        expected = ["todo_write", "todo_read", "write", "read", "list", "glob", "finish_task"]
        assert test_agent.allowed_tools == expected


class TestMessageProcessing:
    """Test the step() method message processing."""

    def test_step_with_user_message(self, test_agent):
        """Test processing a user message."""
        # Create a mock tool call
        mock_tool_call = Mock()
        mock_tool_call.id = "call_1"
        mock_tool_call.name = "todo_write"
        mock_tool_call.arguments = '{"todos": [{"content": "Test", "status": "pending", "activeForm": "Testing"}]}'

        # Create a mock LLM response with tool calls
        mock_response = Mock(spec=LLMResponse)
        mock_response.content = "Let me start by understanding your product vision."
        mock_response.tool_calls = [mock_tool_call]
        test_agent.llm.generate = Mock(return_value=mock_response)

        # Process user message
        user_msg = UserMessage(
            session_id="test_session",
            sequence=0,
            content="I want to build a new product"
        )

        response = test_agent.step(user_msg)

        # Should return ToolCallMessage
        assert isinstance(response, ToolCallMessage)
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].tool_name == "todo_write"

    def test_step_with_tool_result(self, test_agent):
        """Test processing a tool result observation."""
        # Create mock tool call
        mock_tool_call = Mock()
        mock_tool_call.id = "call_2"
        mock_tool_call.name = "write"
        mock_tool_call.arguments = '{"file_path": "docs/PRD.md", "content": "# PRD"}'

        # Mock LLM response
        mock_response = Mock(spec=LLMResponse)
        mock_response.content = "Based on our discussion, I'll create a PRD."
        mock_response.tool_calls = [mock_tool_call]
        test_agent.llm.generate = Mock(return_value=mock_response)

        # Process tool result
        tool_result = ToolResultObservation(
            session_id="test_session",
            sequence=1,
            call_id="call_1",
            content="Todo list updated",
            status="success"
        )

        response = test_agent.step(tool_result)

        assert isinstance(response, ToolCallMessage)
        assert response.tool_calls[0].tool_name == "write"

    def test_step_with_text_response(self, test_agent):
        """Test processing when LLM returns text without tool calls."""
        mock_response = Mock(spec=LLMResponse)
        mock_response.content = "What problem are you trying to solve?"
        mock_response.tool_calls = None
        test_agent.llm.generate = Mock(return_value=mock_response)

        user_msg = UserMessage(
            session_id="test_session",
            sequence=0,
            content="I need help brainstorming"
        )

        response = test_agent.step(user_msg)

        assert isinstance(response, LLMRespondMessage)
        assert "problem" in response.content

    def test_step_when_not_running(self, test_agent):
        """Test that step returns None when agent is not running."""
        test_agent.is_running = False

        user_msg = UserMessage(
            session_id="test_session",
            sequence=0,
            content="Test"
        )

        response = test_agent.step(user_msg)
        assert response is None


class TestFinishTask:
    """Test the finish_task handling."""

    def test_finish_task_with_documentation_summary(self, test_agent):
        """Test that finish_task creates AgentFinishedMessage with documentation summary."""
        documentation_summary = """Documentation Created:
- docs/PRODUCT_REQUIREMENTS.md
- docs/TECHNICAL_SPEC.md

Next Steps:
- Ready for coding agent to implement"""

        # Create mock tool call
        mock_tool_call = Mock()
        mock_tool_call.id = "call_finish"
        mock_tool_call.name = "finish_task"
        mock_tool_call.arguments = json.dumps({
            "reason": "Product requirements complete",
            "result": documentation_summary
        })

        mock_response = Mock(spec=LLMResponse)
        mock_response.content = "Documentation complete."
        mock_response.tool_calls = [mock_tool_call]
        test_agent.llm.generate = Mock(return_value=mock_response)

        user_msg = UserMessage(
            session_id="test_session",
            sequence=0,
            content="Finish up"
        )

        response = test_agent.step(user_msg)

        # Should return AgentFinishedMessage
        assert isinstance(response, AgentFinishedMessage)
        assert documentation_summary in response.reason
        assert "Product requirements complete" in response.reason

        # Agent should no longer be running
        assert test_agent.is_running is False

    def test_finish_task_with_dict_arguments(self, test_agent):
        """Test finish_task with dict arguments instead of JSON string."""
        # Create mock tool call with dict arguments
        mock_tool_call = Mock()
        mock_tool_call.id = "call_finish"
        mock_tool_call.name = "finish_task"
        mock_tool_call.arguments = {
            "reason": "Brainstorming complete",
            "result": "PRD created successfully"
        }

        mock_response = Mock(spec=LLMResponse)
        mock_response.content = "Done."
        mock_response.tool_calls = [mock_tool_call]
        test_agent.llm.generate = Mock(return_value=mock_response)

        user_msg = UserMessage(session_id="test_session", sequence=0, content="Finish")
        response = test_agent.step(user_msg)

        assert isinstance(response, AgentFinishedMessage)
        assert "PRD created successfully" in response.reason

    def test_finish_task_stops_agent(self, test_agent):
        """Test that finish_task sets is_running to False."""
        # Create mock tool call
        mock_tool_call = Mock()
        mock_tool_call.id = "call_finish"
        mock_tool_call.name = "finish_task"
        mock_tool_call.arguments = '{"reason": "Done", "result": "Documentation complete"}'

        mock_response = Mock(spec=LLMResponse)
        mock_response.content = ""
        mock_response.tool_calls = [mock_tool_call]
        test_agent.llm.generate = Mock(return_value=mock_response)

        assert test_agent.is_running is True

        user_msg = UserMessage(session_id="test_session", sequence=0, content="Test")
        test_agent.step(user_msg)

        assert test_agent.is_running is False


class TestPublishCallback:
    """Test that messages are published via callback."""

    def test_tool_call_published(self, test_agent):
        """Test that ToolCallMessage is published."""
        callback = Mock()
        test_agent.publish_callback = callback

        # Create mock tool call
        mock_tool_call = Mock()
        mock_tool_call.id = "call_1"
        mock_tool_call.name = "write"
        mock_tool_call.arguments = '{"file_path": "docs/PRD.md", "content": "test"}'

        mock_response = Mock(spec=LLMResponse)
        mock_response.content = "Creating PRD"
        mock_response.tool_calls = [mock_tool_call]
        test_agent.llm.generate = Mock(return_value=mock_response)

        user_msg = UserMessage(session_id="test_session", sequence=0, content="Test")
        test_agent.step(user_msg)

        callback.assert_called_once()
        assert isinstance(callback.call_args[0][0], ToolCallMessage)

    def test_finished_message_published(self, test_agent):
        """Test that AgentFinishedMessage is published."""
        callback = Mock()
        test_agent.publish_callback = callback

        # Create mock tool call
        mock_tool_call = Mock()
        mock_tool_call.id = "call_finish"
        mock_tool_call.name = "finish_task"
        mock_tool_call.arguments = '{"reason": "Done", "result": "Documentation complete"}'

        mock_response = Mock(spec=LLMResponse)
        mock_response.content = ""
        mock_response.tool_calls = [mock_tool_call]
        test_agent.llm.generate = Mock(return_value=mock_response)

        user_msg = UserMessage(session_id="test_session", sequence=0, content="Test")
        test_agent.step(user_msg)

        callback.assert_called_once()
        assert isinstance(callback.call_args[0][0], AgentFinishedMessage)


class TestDebugLogging:
    """Test debug logging functionality."""

    def test_debug_logging_disabled_by_default(self, test_agent):
        """Test that debug logging is disabled when debug_log_path is None."""
        assert test_agent.debug_log_path is None

    def test_debug_logging_enabled(self, mock_llm, test_project_dir, tmp_path):
        """Test that debug logging writes to file when enabled."""
        log_path = tmp_path / "debug.log"

        agent = ProductManagerAgent(
            session_id="test",
            llm=mock_llm,
            project_directory=str(test_project_dir),
            debug_log_path=str(log_path)
        )

        mock_response = Mock(spec=LLMResponse)
        mock_response.content = "Let's brainstorm"
        mock_response.tool_calls = None
        mock_response.stop_reason = "end_turn"
        mock_response.usage = {"total_tokens": 100}
        agent.llm.generate = Mock(return_value=mock_response)

        user_msg = UserMessage(session_id="test", sequence=0, content="Test")
        agent.step(user_msg)

        # Check that log file was created
        assert log_path.exists()
        content = log_path.read_text(encoding='utf-8')
        assert "test" in content.lower()


class TestSystemPrompt:
    """Test system prompt generation."""

    def test_system_prompt_contains_workflow_phases(self, test_agent):
        """Test that system prompt contains all workflow phases."""
        prompt = test_agent.get_system_message()

        assert "DISCOVERY" in prompt
        assert "EXPLORATION" in prompt
        assert "PRIORITIZATION" in prompt
        assert "DOCUMENTATION" in prompt
        assert "ITERATION" in prompt

    def test_system_prompt_contains_rules(self, test_agent):
        """Test that system prompt contains important rules."""
        prompt = test_agent.get_system_message()

        assert "conversational" in prompt.lower()
        assert "questions" in prompt.lower()
        assert "prd" in prompt.lower() or "product requirements" in prompt.lower()

    def test_system_prompt_contains_tools(self, test_agent):
        """Test that system prompt mentions the tools."""
        prompt = test_agent.get_system_message()

        assert "todo_write" in prompt
        assert "write" in prompt
        assert "read" in prompt
        assert "finish_task" in prompt

    def test_system_prompt_contains_document_templates(self, test_agent):
        """Test that system prompt includes documentation templates."""
        prompt = test_agent.get_system_message()

        assert "PRODUCT_REQUIREMENTS.md" in prompt
        assert "TECHNICAL_SPEC.md" in prompt
        assert "USER_STORIES.md" in prompt


class TestFormatFinishMessage:
    """Test the custom finish message formatting."""

    def test_format_finish_message_includes_both_parts(self, test_agent):
        """Test that finish message includes both reason and result."""
        reason = "Product requirements complete"
        result = """Documentation Created:
- docs/PRD.md
- docs/TECHNICAL_SPEC.md

Next Steps:
- Ready for implementation"""

        formatted = test_agent._format_finish_message(reason, result)

        assert reason in formatted
        assert result in formatted
        assert "docs/PRD.md" in formatted
        assert "Next Steps" in formatted
