"""
Unit tests for CodebaseAnalyzerAgent.

These tests verify the core functionality of the codebase analyzer agent,
including initialization, tool filtering, and message processing.
"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, MagicMock

from agent_framework.agents.codebase_analyzer_agent import CodebaseAnalyzerAgent
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
    src_dir = tmp_path / "src"
    src_dir.mkdir()

    # Create sample files
    (src_dir / "main.py").write_text("print('hello')\n")
    (src_dir / "utils.py").write_text("def helper():\n    pass\n")

    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_main.py").write_text("def test_main():\n    pass\n")

    (tmp_path / "README.md").write_text("# Test Project\n")
    (tmp_path / "requirements.txt").write_text("pytest>=7.0.0\n")

    return tmp_path


@pytest.fixture
def test_agent(mock_llm, test_project_dir):
    """Create a test agent instance."""
    return CodebaseAnalyzerAgent(
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
        assert test_agent.report_format == "markdown"
        assert test_agent.analysis_depth == "standard"

    def test_project_directory_validation(self, mock_llm):
        """Test that invalid project directory raises error."""
        with pytest.raises(ValueError, match="does not exist"):
            CodebaseAnalyzerAgent(
                session_id="test",
                llm=mock_llm,
                project_directory="/nonexistent/path"
            )

    def test_project_directory_not_dir(self, mock_llm, tmp_path):
        """Test that file path instead of directory raises error."""
        file_path = tmp_path / "file.txt"
        file_path.write_text("test")

        with pytest.raises(ValueError, match="not a directory"):
            CodebaseAnalyzerAgent(
                session_id="test",
                llm=mock_llm,
                project_directory=str(file_path)
            )

    def test_default_project_directory(self, mock_llm):
        """Test that agent uses cwd if no directory specified."""
        agent = CodebaseAnalyzerAgent(
            session_id="test",
            llm=mock_llm
        )
        assert agent.project_directory == Path.cwd()

    def test_execution_context_created(self, test_agent, test_project_dir):
        """Test that execution context is properly initialized."""
        assert test_agent.execution_context is not None
        assert test_agent.execution_context.session_id == "test_session"
        assert test_agent.execution_context.working_directory == str(test_project_dir)

    def test_system_message_in_history(self, test_agent, test_project_dir):
        """Test that system message is added to history with formatted prompt."""
        messages = test_agent.history.get_messages()
        assert len(messages) > 0

        system_msg = messages[0]
        assert "SystemMessage" in str(type(system_msg))
        assert str(test_project_dir) in system_msg.content
        assert "Codebase Analyzer Agent" in system_msg.content
        assert "DISCOVER" in system_msg.content
        assert "finish_task" in system_msg.content


class TestToolFiltering:
    """Test that only safe, read-only tools are exposed."""

    def test_allowed_tools_registered(self, test_agent):
        """Test that all required read-only tools are available."""
        required_tools = ["glob", "grep", "read", "list", "todo_write", "todo_read", "finish_task"]

        for tool_name in required_tools:
            tool = test_agent.tools.get(tool_name)
            assert tool is not None, f"Tool {tool_name} should be available"

    def test_write_tools_in_global_registry(self, test_agent):
        """Test that write tools exist in global registry but..."""
        # They exist in the singleton registry
        assert test_agent.tools.get("edit") is not None
        assert test_agent.tools.get("write") is not None

    def test_write_tools_not_in_llm_schema(self, test_agent):
        """Test that write tools are NOT exposed to LLM."""
        schema = test_agent.get_allowed_tools_schema()
        schema_tool_names = [tool['function']['name'] for tool in schema]

        # Verify forbidden tools are NOT in schema
        assert "edit" not in schema_tool_names
        assert "write" not in schema_tool_names
        assert "bash" not in schema_tool_names
        assert "multi_edit" not in schema_tool_names

    def test_only_allowed_tools_in_schema(self, test_agent):
        """Test that LLM schema contains exactly the allowed tools."""
        schema = test_agent.get_allowed_tools_schema()
        schema_tool_names = set([tool['function']['name'] for tool in schema])

        expected_tools = set(test_agent.allowed_tools)
        assert schema_tool_names == expected_tools

    def test_allowed_tools_list(self, test_agent):
        """Test that allowed_tools list is correct."""
        expected = ["glob", "grep", "read", "list", "todo_write", "todo_read", "finish_task"]
        assert test_agent.allowed_tools == expected


class TestMessageProcessing:
    """Test the step() method message processing."""

    def test_step_with_user_message(self, test_agent):
        """Test processing a user message."""
        # Create a mock tool call
        mock_tool_call = Mock()
        mock_tool_call.id = "call_1"
        mock_tool_call.name = "glob"
        mock_tool_call.arguments = '{"pattern": "**/*.py"}'

        # Create a mock LLM response with tool calls
        mock_response = Mock(spec=LLMResponse)
        mock_response.content = "I'll start by discovering the project structure."
        mock_response.tool_calls = [mock_tool_call]
        test_agent.llm.generate = Mock(return_value=mock_response)

        # Process user message
        user_msg = UserMessage(
            session_id="test_session",
            sequence=0,
            content="Analyze this project"
        )

        response = test_agent.step(user_msg)

        # Should return ToolCallMessage
        assert isinstance(response, ToolCallMessage)
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].tool_name == "glob"

    def test_step_with_tool_result(self, test_agent):
        """Test processing a tool result observation."""
        # Create mock tool call
        mock_tool_call = Mock()
        mock_tool_call.id = "call_2"
        mock_tool_call.name = "read"
        mock_tool_call.arguments = '{"file_path": "src/main.py"}'

        # Mock LLM response
        mock_response = Mock(spec=LLMResponse)
        mock_response.content = "I found 3 Python files. Let me read the main file."
        mock_response.tool_calls = [mock_tool_call]
        test_agent.llm.generate = Mock(return_value=mock_response)

        # Process tool result
        tool_result = ToolResultObservation(
            session_id="test_session",
            sequence=1,
            call_id="call_1",
            content="Found 3 files: main.py, utils.py, test_main.py",
            status="success"
        )

        response = test_agent.step(tool_result)

        assert isinstance(response, ToolCallMessage)
        assert response.tool_calls[0].tool_name == "read"

    def test_step_with_text_response(self, test_agent):
        """Test processing when LLM returns text without tool calls."""
        mock_response = Mock(spec=LLMResponse)
        mock_response.content = "I'm analyzing the structure..."
        mock_response.tool_calls = None
        test_agent.llm.generate = Mock(return_value=mock_response)

        user_msg = UserMessage(
            session_id="test_session",
            sequence=0,
            content="Status update?"
        )

        response = test_agent.step(user_msg)

        assert isinstance(response, LLMRespondMessage)
        assert "analyzing" in response.content

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

    def test_finish_task_with_report(self, test_agent):
        """Test that finish_task creates AgentFinishedMessage with report."""
        report_content = "# Analysis Report\n\nThis is a test report."

        # Create mock tool call
        mock_tool_call = Mock()
        mock_tool_call.id = "call_finish"
        mock_tool_call.name = "finish_task"
        mock_tool_call.arguments = json.dumps({
            "reason": "Analysis complete",
            "result": report_content
        })

        mock_response = Mock(spec=LLMResponse)
        mock_response.content = "Analysis complete."
        mock_response.tool_calls = [mock_tool_call]
        test_agent.llm.generate = Mock(return_value=mock_response)

        user_msg = UserMessage(
            session_id="test_session",
            sequence=0,
            content="Generate report"
        )

        response = test_agent.step(user_msg)

        # Should return AgentFinishedMessage
        assert isinstance(response, AgentFinishedMessage)
        assert report_content in response.reason
        assert "Analysis complete" in response.reason

        # Agent should no longer be running
        assert test_agent.is_running is False

    def test_finish_task_with_dict_arguments(self, test_agent):
        """Test finish_task with dict arguments instead of JSON string."""
        # Create mock tool call with dict arguments
        mock_tool_call = Mock()
        mock_tool_call.id = "call_finish"
        mock_tool_call.name = "finish_task"
        mock_tool_call.arguments = {
            "reason": "Task completed",
            "result": "Report here"
        }

        mock_response = Mock(spec=LLMResponse)
        mock_response.content = "Done."
        mock_response.tool_calls = [mock_tool_call]
        test_agent.llm.generate = Mock(return_value=mock_response)

        user_msg = UserMessage(session_id="test_session", sequence=0, content="Finish")
        response = test_agent.step(user_msg)

        assert isinstance(response, AgentFinishedMessage)
        assert "Report here" in response.reason

    def test_finish_task_stops_agent(self, test_agent):
        """Test that finish_task sets is_running to False."""
        # Create mock tool call
        mock_tool_call = Mock()
        mock_tool_call.id = "call_finish"
        mock_tool_call.name = "finish_task"
        mock_tool_call.arguments = '{"reason": "Done", "result": "Report"}'

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
        mock_tool_call.name = "glob"
        mock_tool_call.arguments = '{"pattern": "*.py"}'

        mock_response = Mock(spec=LLMResponse)
        mock_response.content = "Testing"
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
        mock_tool_call.arguments = '{"reason": "Done", "result": "Report"}'

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

        agent = CodebaseAnalyzerAgent(
            session_id="test",
            llm=mock_llm,
            project_directory=str(test_project_dir),
            debug_log_path=str(log_path)
        )

        mock_response = Mock(spec=LLMResponse)
        mock_response.content = "Test"
        mock_response.tool_calls = None
        mock_response.stop_reason = "end_turn"
        mock_response.usage = {"total_tokens": 100}
        agent.llm.generate = Mock(return_value=mock_response)

        user_msg = UserMessage(session_id="test", sequence=0, content="Test")
        agent.step(user_msg)

        # Check that log file was created
        assert log_path.exists()
        content = log_path.read_text(encoding='utf-8')
        assert "test" in content
        assert "Test" in content


class TestSystemPrompt:
    """Test system prompt generation."""

    def test_system_prompt_contains_workflow(self, test_agent):
        """Test that system prompt contains all workflow phases."""
        prompt = test_agent.get_system_message()

        assert "DISCOVER" in prompt
        assert "CATALOG" in prompt
        assert "ANALYZE" in prompt
        assert "MEASURE" in prompt
        assert "REPORT" in prompt

    def test_system_prompt_contains_rules(self, test_agent):
        """Test that system prompt contains safety rules."""
        prompt = test_agent.get_system_message()

        assert "READ-ONLY" in prompt
        assert "SYSTEMATIC" in prompt
        assert "EVIDENCE-BASED" in prompt
        assert "ACTIONABLE" in prompt

    def test_system_prompt_contains_tools(self, test_agent):
        """Test that system prompt mentions the tools."""
        prompt = test_agent.get_system_message()

        assert "glob" in prompt
        assert "grep" in prompt
        assert "read" in prompt
        assert "list" in prompt
        assert "finish_task" in prompt


class TestConfiguration:
    """Test different configuration options."""

    def test_custom_report_format(self, mock_llm, test_project_dir):
        """Test setting custom report format."""
        agent = CodebaseAnalyzerAgent(
            session_id="test",
            llm=mock_llm,
            project_directory=str(test_project_dir),
            report_format="json"
        )
        assert agent.report_format == "json"

    def test_custom_analysis_depth(self, mock_llm, test_project_dir):
        """Test setting custom analysis depth."""
        agent = CodebaseAnalyzerAgent(
            session_id="test",
            llm=mock_llm,
            project_directory=str(test_project_dir),
            analysis_depth="deep"
        )
        assert agent.analysis_depth == "deep"

    def test_custom_tools(self, mock_llm, test_project_dir):
        """Test providing custom tools."""
        from agent_framework.tools.tool_base import ToolRegistry

        custom_tools = ToolRegistry()
        agent = CodebaseAnalyzerAgent(
            session_id="test",
            llm=mock_llm,
            project_directory=str(test_project_dir),
            tools=custom_tools
        )
        assert agent.tools is custom_tools
