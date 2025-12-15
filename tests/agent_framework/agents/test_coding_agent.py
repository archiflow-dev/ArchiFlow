"""Tests for CodingAgent."""
import unittest
from unittest.mock import MagicMock
from src.agent_framework.agents.coding_agent import CodingAgent
from src.agent_framework.config.manager import AgentConfig
from src.agent_framework.messages.types import UserMessage


class TestCodingAgent(unittest.TestCase):
    """Test CodingAgent functionality."""

    def setUp(self):
        # Use MockLLMProvider instead of MagicMock for proper model_config support
        from src.agent_framework.llm.mock import MockLLMProvider
        from src.agent_framework.llm.provider import LLMResponse

        self.mock_llm = MockLLMProvider()
        # Mock generate to return specific response
        self.mock_llm.generate = MagicMock(return_value=LLMResponse(content="I can help with code."))

        self.mock_publish = MagicMock()

        # Use new API: CodingAgent(session_id, llm, ...)
        self.agent = CodingAgent(
            session_id="test_session",
            llm=self.mock_llm,
            publish_callback=self.mock_publish
        )
    
    def test_initialization_registers_tools(self):
        """Test that file tools are registered."""
        tools = self.agent.tools.list_tools()
        
        # Check that tools are registered
        self.assertTrue(len(tools) > 0, "Should have tools registered")
    
    def test_system_message(self):
        """Test system message content."""
        sys_msg = self.agent.history.messages[0]
        # Check for coding agent prompt content
        self.assertIn("Coding Agent", sys_msg.content)
        self.assertIn("project directory", sys_msg.content.lower())
    
    def test_step_execution(self):
        """Test basic step execution."""
        msg = UserMessage(session_id="test_session", sequence=1, content="Write a file")
        self.agent.step(msg)
        
        self.mock_llm.generate.assert_called_once()
        self.mock_publish.assert_called_once()


class TestCodingAgentPRDescription(unittest.TestCase):
    """Test CodingAgent PR description functionality (Phase 1.4-1.5)."""

    def test_pr_description_draft_initialized_on_first_message(self):
        """PR description draft should be created on first user message."""
        from pathlib import Path
        import tempfile
        from src.agent_framework.llm.mock import MockLLMProvider
        from src.agent_framework.llm.provider import LLMResponse
        from src.agent_framework.messages.types import UserMessage

        with tempfile.TemporaryDirectory() as tmpdir:
            llm = MockLLMProvider()
            llm.generate = MagicMock(return_value=LLMResponse(content="Working on it"))

            agent = CodingAgent(
                session_id="test_session",
                llm=llm,
                project_directory=tmpdir
            )

            # Send first user message
            msg = UserMessage(session_id="test_session", sequence=1, content="Add a new feature")
            agent.step(msg)

            # Check that draft was created
            draft_file = Path(tmpdir) / ".agent" / "review" / "pr_description.draft.md"
            self.assertTrue(draft_file.exists(), "PR description draft should be created")

            content = draft_file.read_text()
            self.assertIn("Add a new feature", content)
            self.assertIn("CodingAgent", content)

    def test_pr_description_not_initialized_twice(self):
        """PR description draft should only be initialized once."""
        from pathlib import Path
        import tempfile
        from src.agent_framework.llm.mock import MockLLMProvider
        from src.agent_framework.llm.provider import LLMResponse
        from src.agent_framework.messages.types import UserMessage

        with tempfile.TemporaryDirectory() as tmpdir:
            llm = MockLLMProvider()
            llm.generate = MagicMock(return_value=LLMResponse(content="Working on it"))

            agent = CodingAgent(
                session_id="test_session",
                llm=llm,
                project_directory=tmpdir
            )

            # Send first message
            msg1 = UserMessage(session_id="test_session", sequence=1, content="First task")
            agent.step(msg1)

            draft_file = Path(tmpdir) / ".agent" / "review" / "pr_description.draft.md"
            first_mtime = draft_file.stat().st_mtime

            # Send second message (should NOT reinitialize)
            msg2 = UserMessage(session_id="test_session", sequence=2, content="Second task")
            agent.step(msg2)

            second_mtime = draft_file.stat().st_mtime
            self.assertEqual(first_mtime, second_mtime, "Draft should not be recreated")

    def test_final_pr_description_generated_on_finish(self):
        """Final PR description should be generated when finish_task is called."""
        from pathlib import Path
        import tempfile
        import json
        from src.agent_framework.llm.mock import MockLLMProvider
        from src.agent_framework.llm.provider import LLMResponse
        from unittest.mock import MagicMock, patch

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create draft first
            draft_dir = Path(tmpdir) / ".agent" / "review"
            draft_dir.mkdir(parents=True)
            draft_file = draft_dir / "pr_description.draft.md"
            draft_file.write_text("## What was requested\nAdd feature X")

            # Mock LLM
            llm = MockLLMProvider()
            mock_generate = MagicMock(return_value=LLMResponse(
                content="# Pull Request\n\n## Summary\nAdded feature X\n\n## Changes\n- Implemented X"
            ))
            llm.generate = mock_generate

            agent = CodingAgent(
                session_id="test_session",
                llm=llm,
                project_directory=tmpdir
            )

            # Create mock tool call for finish_task
            class MockToolCall:
                def __init__(self):
                    self.name = "finish_task"
                    self.arguments = {"reason": "Task completed", "result": ""}

            # Call _handle_finish_task directly
            tool_calls = [MockToolCall()]
            result = agent._handle_finish_task(tool_calls)

            # Verify final PR description was generated
            pr_file = draft_dir / "pr_description.md"
            self.assertTrue(pr_file.exists(), "Final PR description should be created")

            content = pr_file.read_text()
            self.assertIn("Pull Request", content)
            self.assertIn("Added feature X", content)

            # Verify LLM was called for generation
            self.assertTrue(mock_generate.called, "LLM should be called to generate PR description")

            # Verify agent finished
            self.assertIsNotNone(result)
            self.assertFalse(agent.is_running)


class TestCodingAgentProjectDirectory(unittest.TestCase):
    """Test CodingAgent project directory functionality."""

    def test_default_project_directory(self):
        """CodingAgent should default to current working directory."""
        from pathlib import Path
        from src.agent_framework.llm.mock import MockLLMProvider

        llm = MockLLMProvider()
        agent = CodingAgent(session_id="test", llm=llm)

        self.assertEqual(agent.project_directory, Path.cwd())
        self.assertEqual(agent.execution_context.working_directory, str(Path.cwd()))

    def test_custom_project_directory(self):
        """CodingAgent should accept custom project directory."""
        from pathlib import Path
        import tempfile
        from src.agent_framework.llm.mock import MockLLMProvider

        with tempfile.TemporaryDirectory() as tmpdir:
            llm = MockLLMProvider()
            agent = CodingAgent(
                session_id="test",
                llm=llm,
                project_directory=tmpdir
            )

            self.assertEqual(agent.project_directory, Path(tmpdir).resolve())
            self.assertEqual(agent.execution_context.working_directory, str(Path(tmpdir).resolve()))

    def test_nonexistent_directory_raises_error(self):
        """CodingAgent should raise error for non-existent directory."""
        from src.agent_framework.llm.mock import MockLLMProvider

        llm = MockLLMProvider()

        with self.assertRaises(ValueError) as ctx:
            CodingAgent(
                session_id="test",
                llm=llm,
                project_directory="/nonexistent/path"
            )
        self.assertIn("does not exist", str(ctx.exception))

    def test_file_as_directory_raises_error(self):
        """CodingAgent should raise error if directory is actually a file."""
        from pathlib import Path
        import tempfile
        from src.agent_framework.llm.mock import MockLLMProvider

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file
            file_path = Path(tmpdir) / "file.txt"
            file_path.write_text("test")

            llm = MockLLMProvider()

            with self.assertRaises(ValueError) as ctx:
                CodingAgent(
                    session_id="test",
                    llm=llm,
                    project_directory=str(file_path)
                )
            self.assertIn("not a directory", str(ctx.exception))

    def test_system_prompt_includes_project_directory(self):
        """System prompt should include project directory information."""
        from pathlib import Path
        import tempfile
        from src.agent_framework.llm.mock import MockLLMProvider

        with tempfile.TemporaryDirectory() as tmpdir:
            llm = MockLLMProvider()
            agent = CodingAgent(
                session_id="test",
                llm=llm,
                project_directory=tmpdir
            )

            # Check that system message includes project directory
            system_msg = agent.history.messages[0]
            self.assertIn(tmpdir, system_msg.content)
            self.assertIn("project directory", system_msg.content.lower())


if __name__ == '__main__':
    unittest.main()
