"""
Unit tests for ProjectAgent base class.

Tests the common functionality provided by ProjectAgent that is shared
by CodingAgent and CodebaseAnalyzerAgent.
"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

from agent_framework.agents.project_agent import ProjectAgent
from agent_framework.llm.mock import MockLLMProvider
from agent_framework.llm.provider import LLMResponse
from agent_framework.messages.types import (
    UserMessage, ToolResultObservation, AgentFinishedMessage,
    ToolCallMessage, LLMRespondMessage
)
from agent_framework.tools.tool_base import ToolRegistry


class ConcreteProjectAgent(ProjectAgent):
    """
    Concrete implementation of ProjectAgent for testing.
    """

    SYSTEM_PROMPT = """Test Agent. Project directory: {project_directory}"""

    def get_system_message(self) -> str:
        return self.SYSTEM_PROMPT

    def _setup_tools(self):
        """Setup is tested separately."""
        pass

    def _get_tools_schema(self):
        """Return all tools."""
        return self.tools.to_llm_schema()


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
    (src_dir / "main.py").write_text("print('hello')\n")

    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_main.py").write_text("def test_main():\n    pass\n")

    (tmp_path / "README.md").write_text("# Test Project\n")

    return tmp_path


@pytest.fixture
def test_agent(mock_llm, test_project_dir):
    """Create a test agent instance."""
    return ConcreteProjectAgent(
        session_id="test_session",
        llm=mock_llm,
        project_directory=str(test_project_dir)
    )


class TestProjectAgentInitialization:
    """Test ProjectAgent initialization and setup."""

    def test_agent_creation(self, test_agent, test_project_dir):
        """Test that agent can be created successfully."""
        assert test_agent.session_id == "test_session"
        assert test_agent.project_directory == test_project_dir
        assert test_agent.is_running is True
        assert test_agent.sequence_counter == 1  # System message added

    def test_project_directory_defaults_to_cwd(self, mock_llm):
        """Test that project_directory defaults to current directory."""
        agent = ConcreteProjectAgent(
            session_id="test",
            llm=mock_llm,
            project_directory=None
        )
        assert agent.project_directory == Path.cwd()

    def test_project_directory_validation_nonexistent(self, mock_llm):
        """Test that invalid project directory raises error."""
        with pytest.raises(ValueError, match="does not exist"):
            ConcreteProjectAgent(
                session_id="test",
                llm=mock_llm,
                project_directory="/nonexistent/path"
            )

    def test_project_directory_validation_not_dir(self, mock_llm, tmp_path):
        """Test that file path instead of directory raises error."""
        file_path = tmp_path / "file.txt"
        file_path.write_text("test")

        with pytest.raises(ValueError, match="not a directory"):
            ConcreteProjectAgent(
                session_id="test",
                llm=mock_llm,
                project_directory=str(file_path)
            )

    def test_execution_context_created(self, test_agent, test_project_dir):
        """Test that execution context is properly initialized."""
        assert test_agent.execution_context is not None
        assert test_agent.execution_context.session_id == "test_session"
        assert test_agent.execution_context.working_directory == str(test_project_dir)

    def test_system_message_added(self, test_agent, test_project_dir):
        """Test that system message is added to history with formatted prompt."""
        messages = test_agent.history.get_messages()
        assert len(messages) > 0

        system_msg = messages[0]
        assert "SystemMessage" in str(type(system_msg))
        assert str(test_project_dir) in system_msg.content
        assert "Test Agent" in system_msg.content

    def test_sequence_counter_initialized(self, test_agent):
        """Test that sequence counter is initialized."""
        # Counter should be 1 after system message
        assert test_agent.sequence_counter == 1

    def test_debug_log_path_optional(self, mock_llm, test_project_dir):
        """Test that debug_log_path is optional."""
        agent = ConcreteProjectAgent(
            session_id="test",
            llm=mock_llm,
            project_directory=str(test_project_dir),
            debug_log_path=None
        )
        assert agent.debug_log_path is None

    def test_debug_log_path_set(self, mock_llm, test_project_dir, tmp_path):
        """Test that debug_log_path can be set."""
        log_path = tmp_path / "debug.log"
        agent = ConcreteProjectAgent(
            session_id="test",
            llm=mock_llm,
            project_directory=str(test_project_dir),
            debug_log_path=str(log_path)
        )
        assert agent.debug_log_path == str(log_path)

    def test_publish_callback_optional(self, mock_llm, test_project_dir):
        """Test that publish_callback is optional."""
        agent = ConcreteProjectAgent(
            session_id="test",
            llm=mock_llm,
            project_directory=str(test_project_dir),
            publish_callback=None
        )
        assert agent.publish_callback is None

    def test_agent_name_and_version(self, mock_llm, test_project_dir):
        """Test that agent_name and agent_version are used in config."""
        agent = ConcreteProjectAgent(
            session_id="test",
            llm=mock_llm,
            project_directory=str(test_project_dir),
            agent_name="TestAgent",
            agent_version="2.0.0"
        )
        assert agent.config["name"] == "TestAgent"
        assert agent.config["version"] == "2.0.0"


class TestSequenceCounter:
    """Test sequence counter functionality."""

    def test_next_sequence_increments(self, test_agent):
        """Test that _next_sequence increments counter."""
        seq1 = test_agent._next_sequence()
        seq2 = test_agent._next_sequence()
        seq3 = test_agent._next_sequence()

        assert seq2 == seq1 + 1
        assert seq3 == seq2 + 1

    def test_next_sequence_starts_after_system_message(self, test_agent):
        """Test that counter accounts for system message."""
        # System message uses sequence 0
        # Next call should return 1
        seq = test_agent._next_sequence()
        assert seq == 1


class TestDebugLogging:
    """Test debug logging functionality."""

    def test_debug_logging_disabled_by_default(self, test_agent):
        """Test that debug logging is disabled when debug_log_path is None."""
        assert test_agent.debug_log_path is None

        # Should not raise error when logging is disabled
        test_agent._log_debug_info([], [], Mock())

    def test_debug_logging_creates_file(self, mock_llm, test_project_dir, tmp_path):
        """Test that debug logging creates log file."""
        log_path = tmp_path / "debug.log"

        agent = ConcreteProjectAgent(
            session_id="test",
            llm=mock_llm,
            project_directory=str(test_project_dir),
            debug_log_path=str(log_path)
        )

        # Create mock response
        mock_response = Mock(spec=LLMResponse)
        mock_response.content = "Test response"
        mock_response.tool_calls = None
        mock_response.stop_reason = "end_turn"
        mock_response.usage = {"total_tokens": 100}

        # Log debug info
        agent._log_debug_info(
            messages=[{"role": "user", "content": "test"}],
            tools_schema=[],
            response=mock_response
        )

        # Check that log file was created
        assert log_path.exists()
        content = log_path.read_text(encoding='utf-8')
        assert "test" in content
        assert "Test response" in content

    def test_debug_logging_creates_parent_directories(self, mock_llm, test_project_dir, tmp_path):
        """Test that debug logging creates parent directories."""
        log_path = tmp_path / "nested" / "dirs" / "debug.log"

        agent = ConcreteProjectAgent(
            session_id="test",
            llm=mock_llm,
            project_directory=str(test_project_dir),
            debug_log_path=str(log_path)
        )

        mock_response = Mock(spec=LLMResponse)
        mock_response.content = "Test"
        mock_response.tool_calls = None
        mock_response.stop_reason = "end_turn"
        mock_response.usage = {}

        agent._log_debug_info([], [], mock_response)

        assert log_path.exists()
        assert log_path.parent.exists()


class TestFinishTaskHandling:
    """Test finish_task detection and handling."""

    def test_handle_finish_task_detects_finish(self, test_agent):
        """Test that _handle_finish_task detects finish_task tool call."""
        mock_tool_call = Mock()
        mock_tool_call.name = "finish_task"
        mock_tool_call.arguments = json.dumps({
            "reason": "Task completed",
            "result": "Success"
        })

        result = test_agent._handle_finish_task([mock_tool_call])

        assert isinstance(result, AgentFinishedMessage)
        assert "Task completed" in result.reason
        assert test_agent.is_running is False

    def test_handle_finish_task_with_dict_arguments(self, test_agent):
        """Test finish_task with dict arguments instead of JSON string."""
        mock_tool_call = Mock()
        mock_tool_call.name = "finish_task"
        mock_tool_call.arguments = {
            "reason": "Done",
            "result": "Report here"
        }

        result = test_agent._handle_finish_task([mock_tool_call])

        assert isinstance(result, AgentFinishedMessage)
        assert "Done" in result.reason

    def test_handle_finish_task_returns_none_if_not_found(self, test_agent):
        """Test that _handle_finish_task returns None if no finish_task."""
        mock_tool_call = Mock()
        mock_tool_call.name = "other_tool"

        result = test_agent._handle_finish_task([mock_tool_call])

        assert result is None
        assert test_agent.is_running is True

    def test_handle_finish_task_stops_agent(self, test_agent):
        """Test that finish_task sets is_running to False."""
        mock_tool_call = Mock()
        mock_tool_call.name = "finish_task"
        mock_tool_call.arguments = '{"reason": "Done"}'

        assert test_agent.is_running is True

        test_agent._handle_finish_task([mock_tool_call])

        assert test_agent.is_running is False

    def test_handle_finish_task_publishes_message(self, mock_llm, test_project_dir):
        """Test that finish_task publishes AgentFinishedMessage."""
        callback = Mock()
        agent = ConcreteProjectAgent(
            session_id="test",
            llm=mock_llm,
            project_directory=str(test_project_dir),
            publish_callback=callback
        )

        mock_tool_call = Mock()
        mock_tool_call.name = "finish_task"
        mock_tool_call.arguments = '{"reason": "Complete"}'

        agent._handle_finish_task([mock_tool_call])

        callback.assert_called_once()
        assert isinstance(callback.call_args[0][0], AgentFinishedMessage)


class TestFormatFinishMessage:
    """Test finish message formatting."""

    def test_format_finish_message_default(self, test_agent):
        """Test default finish message format (reason only)."""
        result = test_agent._format_finish_message("Task done", "Report content")
        assert result == "Task done"

    def test_format_finish_message_can_be_overridden(self, mock_llm, test_project_dir):
        """Test that subclasses can override _format_finish_message."""
        class CustomFormatAgent(ConcreteProjectAgent):
            def _format_finish_message(self, reason, result):
                return f"{reason}\n\n{result}"

        agent = CustomFormatAgent(
            session_id="test",
            llm=mock_llm,
            project_directory=str(test_project_dir)
        )

        result = agent._format_finish_message("Done", "Report")
        assert result == "Done\n\nReport"


class TestMessageProcessing:
    """Test message processing in step() method."""

    def test_step_with_user_message(self, test_agent):
        """Test processing a user message."""
        # Create mock tool call
        mock_tool_call = Mock()
        mock_tool_call.id = "call_1"
        mock_tool_call.name = "read"
        mock_tool_call.arguments = '{"file_path": "test.py"}'

        # Create mock LLM response
        mock_response = Mock(spec=LLMResponse)
        mock_response.content = "I'll read the file."
        mock_response.tool_calls = [mock_tool_call]
        test_agent.llm.generate = Mock(return_value=mock_response)

        # Process user message
        user_msg = UserMessage(
            session_id="test_session",
            sequence=1,
            content="Read test.py"
        )

        response = test_agent.step(user_msg)

        # Should return ToolCallMessage
        assert isinstance(response, ToolCallMessage)
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].tool_name == "read"

    def test_step_with_tool_result(self, test_agent):
        """Test processing a tool result observation."""
        # Create mock tool call
        mock_tool_call = Mock()
        mock_tool_call.id = "call_2"
        mock_tool_call.name = "read"
        mock_tool_call.arguments = '{"file_path": "test.py"}'

        # Mock LLM response
        mock_response = Mock(spec=LLMResponse)
        mock_response.content = "The file contains..."
        mock_response.tool_calls = [mock_tool_call]
        test_agent.llm.generate = Mock(return_value=mock_response)

        # Process tool result
        tool_result = ToolResultObservation(
            session_id="test_session",
            sequence=2,
            call_id="call_1",
            content="File content here",
            status="success"
        )

        response = test_agent.step(tool_result)

        assert isinstance(response, ToolCallMessage)

    def test_step_with_text_response(self, test_agent):
        """Test processing when LLM returns text without tool calls."""
        mock_response = Mock(spec=LLMResponse)
        mock_response.content = "I'm analyzing the structure..."
        mock_response.tool_calls = None
        test_agent.llm.generate = Mock(return_value=mock_response)

        user_msg = UserMessage(
            session_id="test_session",
            sequence=1,
            content="Status?"
        )

        response = test_agent.step(user_msg)

        assert isinstance(response, LLMRespondMessage)
        assert "analyzing" in response.content

    def test_step_when_not_running(self, test_agent):
        """Test that step returns None when agent is not running."""
        test_agent.is_running = False

        user_msg = UserMessage(
            session_id="test_session",
            sequence=1,
            content="Test"
        )

        response = test_agent.step(user_msg)
        assert response is None

    def test_step_with_finish_task(self, test_agent):
        """Test that step handles finish_task correctly."""
        mock_tool_call = Mock()
        mock_tool_call.id = "call_finish"
        mock_tool_call.name = "finish_task"
        mock_tool_call.arguments = json.dumps({
            "reason": "Analysis complete",
            "result": "Report content"
        })

        mock_response = Mock(spec=LLMResponse)
        mock_response.content = "Finishing"
        mock_response.tool_calls = [mock_tool_call]
        test_agent.llm.generate = Mock(return_value=mock_response)

        user_msg = UserMessage(
            session_id="test_session",
            sequence=1,
            content="Generate report"
        )

        response = test_agent.step(user_msg)

        # Should return AgentFinishedMessage
        assert isinstance(response, AgentFinishedMessage)
        assert "Analysis complete" in response.reason

        # Agent should no longer be running
        assert test_agent.is_running is False

    def test_step_llm_error_handling(self, test_agent):
        """Test that step handles LLM errors gracefully."""
        test_agent.llm.generate = Mock(side_effect=Exception("LLM error"))

        user_msg = UserMessage(
            session_id="test_session",
            sequence=1,
            content="Test"
        )

        response = test_agent.step(user_msg)
        assert response is None


class TestToolCallProcessing:
    """Test tool call processing."""

    def test_process_tool_calls_creates_tool_call_message(self, test_agent):
        """Test that _process_tool_calls creates ToolCallMessage."""
        mock_tool_call = Mock()
        mock_tool_call.id = "call_1"
        mock_tool_call.name = "read"
        mock_tool_call.arguments = '{"file_path": "test.py"}'

        mock_response = Mock()
        mock_response.content = "Reading file"
        mock_response.tool_calls = [mock_tool_call]

        result = test_agent._process_tool_calls(mock_response)

        assert isinstance(result, ToolCallMessage)
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].tool_name == "read"

    def test_process_tool_calls_with_finish_task(self, test_agent):
        """Test that _process_tool_calls detects finish_task."""
        mock_tool_call = Mock()
        mock_tool_call.id = "call_finish"
        mock_tool_call.name = "finish_task"
        mock_tool_call.arguments = '{"reason": "Done"}'

        mock_response = Mock()
        mock_response.content = ""
        mock_response.tool_calls = [mock_tool_call]

        result = test_agent._process_tool_calls(mock_response)

        assert isinstance(result, AgentFinishedMessage)

    def test_process_tool_calls_returns_none_if_no_calls(self, test_agent):
        """Test that _process_tool_calls returns None if no tool calls."""
        mock_response = Mock()
        mock_response.tool_calls = None

        result = test_agent._process_tool_calls(mock_response)
        assert result is None


class TestTextResponseProcessing:
    """Test text response processing."""

    def test_process_text_response_creates_message(self, test_agent):
        """Test that _process_text_response creates LLMRespondMessage."""
        mock_response = Mock()
        mock_response.content = "This is a text response"

        result = test_agent._process_text_response(mock_response)

        assert isinstance(result, LLMRespondMessage)
        assert result.content == "This is a text response"

    def test_process_text_response_returns_none_if_no_content(self, test_agent):
        """Test that _process_text_response returns None if no content."""
        mock_response = Mock()
        mock_response.content = None

        result = test_agent._process_text_response(mock_response)
        assert result is None

    def test_process_text_response_returns_none_if_empty_content(self, test_agent):
        """Test that _process_text_response returns None if empty content."""
        mock_response = Mock()
        mock_response.content = ""

        result = test_agent._process_text_response(mock_response)
        assert result is None


class TestPublishCallback:
    """Test that messages are published via callback."""

    def test_tool_call_published(self, mock_llm, test_project_dir):
        """Test that ToolCallMessage is published."""
        callback = Mock()
        agent = ConcreteProjectAgent(
            session_id="test",
            llm=mock_llm,
            project_directory=str(test_project_dir),
            publish_callback=callback
        )

        mock_tool_call = Mock()
        mock_tool_call.id = "call_1"
        mock_tool_call.name = "read"
        mock_tool_call.arguments = '{"file_path": "test.py"}'

        mock_response = Mock(spec=LLMResponse)
        mock_response.content = "Reading"
        mock_response.tool_calls = [mock_tool_call]
        agent.llm.generate = Mock(return_value=mock_response)

        user_msg = UserMessage(session_id="test", sequence=1, content="Test")
        agent.step(user_msg)

        callback.assert_called_once()
        assert isinstance(callback.call_args[0][0], ToolCallMessage)

    def test_text_response_published(self, mock_llm, test_project_dir):
        """Test that LLMRespondMessage is published."""
        callback = Mock()
        agent = ConcreteProjectAgent(
            session_id="test",
            llm=mock_llm,
            project_directory=str(test_project_dir),
            publish_callback=callback
        )

        mock_response = Mock(spec=LLMResponse)
        mock_response.content = "Text response"
        mock_response.tool_calls = None
        agent.llm.generate = Mock(return_value=mock_response)

        user_msg = UserMessage(session_id="test", sequence=1, content="Test")
        agent.step(user_msg)

        callback.assert_called_once()
        assert isinstance(callback.call_args[0][0], LLMRespondMessage)


class TestAbstractMethods:
    """Test that abstract methods must be implemented."""

    def test_cannot_instantiate_project_agent_directly(self, mock_llm, test_project_dir):
        """Test that ProjectAgent cannot be instantiated directly."""
        with pytest.raises(TypeError):
            ProjectAgent(
                session_id="test",
                llm=mock_llm,
                project_directory=str(test_project_dir)
            )

    def test_subclass_must_implement_get_system_message(self, mock_llm, test_project_dir):
        """Test that subclass must implement get_system_message."""
        class IncompleteAgent(ProjectAgent):
            def _setup_tools(self):
                pass

            def _get_tools_schema(self):
                return []

        with pytest.raises(TypeError):
            IncompleteAgent(
                session_id="test",
                llm=mock_llm,
                project_directory=str(test_project_dir)
            )

    def test_subclass_must_implement_setup_tools(self, mock_llm, test_project_dir):
        """Test that subclass must implement _setup_tools."""
        class IncompleteAgent(ProjectAgent):
            def get_system_message(self):
                return "Test"

            def _get_tools_schema(self):
                return []

        # Should fail - _setup_tools is abstract and must be implemented
        with pytest.raises(TypeError):
            IncompleteAgent(
                session_id="test",
                llm=mock_llm,
                project_directory=str(test_project_dir)
            )

    def test_subclass_must_implement_get_tools_schema(self, mock_llm, test_project_dir):
        """Test that subclass must implement _get_tools_schema."""
        class IncompleteAgent(ProjectAgent):
            def get_system_message(self):
                return "Test"

            def _setup_tools(self):
                pass

        with pytest.raises(TypeError):
            IncompleteAgent(
                session_id="test",
                llm=mock_llm,
                project_directory=str(test_project_dir)
            )
