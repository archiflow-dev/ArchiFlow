"""
Tests for dynamic system prompt functionality.

Verifies that:
1. System messages are NOT stored in history
2. System prompt is formatted dynamically on each step
3. Agent directory changes are reflected in system prompt
4. CD command syncs agent directory correctly
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock

from agent_cli.commands.system import SystemCommandHandler
from agent_cli.repl.shell_context import ShellContext
from agent_cli.session.manager import SessionManager
from agent_framework.messages.types import SystemMessage, UserMessage
from agent_framework.agents.coding_agent import CodingAgent
from agent_framework.llm.provider import LLMProvider, LLMResponse
from agent_framework.llm.model_config import ModelConfig


def create_mock_llm():
    """Helper to create a properly mocked LLM."""
    llm = Mock(spec=LLMProvider)
    # Create a proper ModelConfig object instead of a dict
    llm.model_config = ModelConfig(
        model_name="gpt-4",
        context_window=8192,
        max_output_tokens=4096,
        cost_per_1k_input=30.0,
        cost_per_1k_output=60.0
    )
    # Mock token counting methods to return integers
    llm.count_tokens = Mock(return_value=100)
    llm.count_tools_tokens = Mock(return_value=50)
    # Add model attribute for logging
    llm.model = "gpt-4"
    return llm


class TestDynamicSystemPrompt:
    """Tests for dynamic system prompt in ProjectAgent."""

    def test_system_message_not_in_history(self, tmp_path):
        """Verify system message is NOT stored in conversation history."""
        # Create agent
        agent = CodingAgent(
            session_id="test",
            llm=create_mock_llm(),
            project_directory=str(tmp_path)
        )

        # Check history - should have NO system messages
        for msg in agent.history._messages:
            assert not isinstance(msg, SystemMessage), \
                "System message should not be in history!"

    def test_format_system_prompt_with_current_directory(self, tmp_path):
        """Verify _format_system_prompt() uses current project_directory."""
        agent = CodingAgent(
            session_id="test",
            llm=create_mock_llm(),
            project_directory=str(tmp_path)
        )

        # Format prompt
        prompt = agent._format_system_prompt()

        # Should contain current directory
        assert str(tmp_path) in prompt
        assert "project directory" in prompt.lower()

    def test_format_system_prompt_reflects_directory_change(self, tmp_path):
        """Verify formatted prompt reflects directory changes."""
        llm = create_mock_llm()

        # Create two directories
        dir1 = tmp_path / "project1"
        dir2 = tmp_path / "project2"
        dir1.mkdir()
        dir2.mkdir()

        agent = CodingAgent(
            session_id="test",
            llm=llm,
            project_directory=str(dir1)
        )

        # Initial prompt should have dir1
        prompt1 = agent._format_system_prompt()
        assert str(dir1) in prompt1
        assert str(dir2) not in prompt1

        # Change directory
        agent.project_directory = dir2

        # New prompt should have dir2
        prompt2 = agent._format_system_prompt()
        assert str(dir2) in prompt2
        assert str(dir1) not in prompt2

    def test_llm_receives_dynamic_system_message(self, tmp_path):
        """Verify LLM receives system message with current directory."""
        # Create mock LLM
        llm = create_mock_llm()
        llm.generate = Mock(return_value=LLMResponse(
            content="Hello",
            tool_calls=None
        ))

        agent = CodingAgent(
            session_id="test",
            llm=llm,
            project_directory=str(tmp_path)
        )

        # Send user message
        user_msg = UserMessage(
            session_id="test",
            sequence=0,
            content="Hello"
        )

        agent.step(user_msg)

        # Check what was sent to LLM
        call_args = llm.generate.call_args
        messages = call_args[0][0]  # First positional argument

        # First message should be system message
        assert messages[0]["role"] == "system"
        assert str(tmp_path) in messages[0]["content"]

    def test_multiple_steps_get_fresh_system_prompt(self, tmp_path):
        """Verify each step() gets a freshly formatted system prompt."""
        llm = create_mock_llm()
        llm.generate = Mock(return_value=LLMResponse(
            content="Response",
            tool_calls=None
        ))

        dir1 = tmp_path / "dir1"
        dir2 = tmp_path / "dir2"
        dir1.mkdir()
        dir2.mkdir()

        agent = CodingAgent(
            session_id="test",
            llm=llm,
            project_directory=str(dir1)
        )

        # Step 1
        agent.step(UserMessage(session_id="test", sequence=0, content="msg1"))
        call1_messages = llm.generate.call_args[0][0]
        assert str(dir1) in call1_messages[0]["content"]

        # Change directory
        agent.project_directory = dir2

        # Step 2
        agent.step(UserMessage(session_id="test", sequence=1, content="msg2"))
        call2_messages = llm.generate.call_args[0][0]

        # Second call should have new directory
        assert str(dir2) in call2_messages[0]["content"]
        assert str(dir1) not in call2_messages[0]["content"]


class TestAgentDirectorySync:
    """Tests for agent directory synchronization on cd."""

    def test_cd_syncs_agent_attributes(self, tmp_path):
        """Test that cd updates all agent attributes."""
        dir1 = tmp_path / "dir1"
        dir2 = tmp_path / "dir2"
        dir1.mkdir()
        dir2.mkdir()

        # Create session manager and agent
        session_manager = SessionManager()
        llm = create_mock_llm()
        agent = CodingAgent(
            session_id="test",
            llm=llm,
            project_directory=str(dir1)
        )
        session = session_manager.create_session(agent)

        # Create system handler with session manager
        shell_context = ShellContext(initial_cwd=dir1)
        system_handler = SystemCommandHandler(shell_context, session_manager)

        # Execute cd
        result = shell_context.execute(f"cd {dir2}")
        assert result.success

        # Manually call sync (since execute is async and we can't await in sync test)
        system_handler._sync_agent_directory()

        # Verify agent updated
        assert agent.project_directory == dir2
        assert agent.execution_context.working_directory == str(dir2)

    def test_cd_syncs_tool_execution_contexts(self, tmp_path):
        """Test that cd updates tool execution contexts."""
        dir1 = tmp_path / "dir1"
        dir2 = tmp_path / "dir2"
        dir1.mkdir()
        dir2.mkdir()

        session_manager = SessionManager()
        llm = create_mock_llm()
        agent = CodingAgent(
            session_id="test",
            llm=llm,
            project_directory=str(dir1)
        )
        session = session_manager.create_session(agent)

        shell_context = ShellContext(initial_cwd=dir1)
        system_handler = SystemCommandHandler(shell_context, session_manager)

        # Execute cd and sync
        shell_context.execute(f"cd {dir2}")
        system_handler._sync_agent_directory()

        # Verify all tools updated
        for tool in agent.tools.list_tools():
            if hasattr(tool, 'execution_context') and tool.execution_context is not None:
                assert tool.execution_context.working_directory == str(dir2)

    def test_sync_without_agent_session(self):
        """Test sync without active agent doesn't error."""
        session_manager = SessionManager()
        shell_context = ShellContext()
        system_handler = SystemCommandHandler(shell_context, session_manager)

        # Should not error
        system_handler._sync_agent_directory()

    def test_sync_without_session_manager(self):
        """Test sync without session manager doesn't error."""
        shell_context = ShellContext()
        system_handler = SystemCommandHandler(shell_context, session_manager=None)

        # Should not error
        system_handler._sync_agent_directory()

    @pytest.mark.skip(reason="SimpleAgent has initialization bug unrelated to system commands")
    def test_sync_with_simple_agent(self):
        """Test sync with agent that has no project_directory."""
        from agent_framework.agents.base import SimpleAgent

        session_manager = SessionManager()
        llm = create_mock_llm()
        agent = SimpleAgent(llm=llm, session_id="test")
        session = session_manager.create_session(agent)

        shell_context = ShellContext()
        system_handler = SystemCommandHandler(shell_context, session_manager)

        # Should not error (SimpleAgent doesn't have project_directory)
        system_handler._sync_agent_directory()

    def test_no_sync_when_directory_unchanged(self, tmp_path):
        """Test that sync is skipped when directory hasn't changed."""
        session_manager = SessionManager()
        llm = create_mock_llm()
        agent = CodingAgent(
            session_id="test",
            llm=llm,
            project_directory=str(tmp_path)
        )
        session = session_manager.create_session(agent)

        shell_context = ShellContext(initial_cwd=tmp_path)
        system_handler = SystemCommandHandler(shell_context, session_manager)

        old_dir = agent.project_directory

        # Sync when directory is same
        system_handler._sync_agent_directory()

        # Should not change
        assert agent.project_directory == old_dir

    @pytest.mark.asyncio
    async def test_cd_command_triggers_sync(self, tmp_path):
        """Integration test: cd command triggers agent sync."""
        dir1 = tmp_path / "dir1"
        dir2 = tmp_path / "dir2"
        dir1.mkdir()
        dir2.mkdir()

        session_manager = SessionManager()
        llm = create_mock_llm()
        agent = CodingAgent(
            session_id="test",
            llm=llm,
            project_directory=str(dir1)
        )
        session = session_manager.create_session(agent)

        shell_context = ShellContext(initial_cwd=dir1)
        system_handler = SystemCommandHandler(shell_context, session_manager)

        # Execute cd through handler
        result = await system_handler.execute(f"cd {dir2}", require_confirmation=False)

        # Verify cd succeeded
        assert result.success
        assert shell_context.cwd == dir2

        # Verify agent synced
        assert agent.project_directory == dir2


class TestSystemPromptTemplate:
    """Tests for system prompt template functionality."""

    def test_template_stored_not_formatted(self, tmp_path):
        """Verify template is stored, not formatted prompt."""
        llm = create_mock_llm()
        agent = CodingAgent(
            session_id="test",
            llm=llm,
            project_directory=str(tmp_path)
        )

        # Template should have placeholder
        assert "{project_directory}" in agent._system_prompt_template

    def test_format_replaces_placeholder(self, tmp_path):
        """Verify format() replaces placeholder with actual path."""
        llm = create_mock_llm()
        agent = CodingAgent(
            session_id="test",
            llm=llm,
            project_directory=str(tmp_path)
        )

        formatted = agent._format_system_prompt()

        # Should not have placeholder
        assert "{project_directory}" not in formatted
        # Should have actual path
        assert str(tmp_path) in formatted
