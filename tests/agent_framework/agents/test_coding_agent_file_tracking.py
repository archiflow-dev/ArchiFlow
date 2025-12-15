"""
Tests for CodingAgent file tracking functionality.

These tests verify that the CodingAgent correctly tracks file modifications
even in non-git repositories, providing a fallback mechanism for PR description
generation.
"""

import pytest
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

from agent_framework.agents.coding_agent import CodingAgent
from agent_framework.llm.provider import LLMProvider, LLMResponse, FinishReason
from agent_framework.messages.types import UserMessage, ToolResultObservation


class MockLLMProvider(LLMProvider):
    """Mock LLM provider for testing."""

    def __init__(self, model: str = "mock", **kwargs):
        super().__init__(model, **kwargs)
        self.responses = []
        self.call_count = 0

    def add_response(self, content: str = None, tool_calls: list = None, finish_reason: FinishReason = FinishReason.STOP):
        """Add a canned response."""
        self.responses.append(LLMResponse(
            content=content,
            tool_calls=tool_calls or [],
            finish_reason=finish_reason,
            usage={"prompt_tokens": 10, "completion_tokens": 20}
        ))

    def generate(self, messages, tools=None, **kwargs):
        """Return next canned response."""
        if self.call_count >= len(self.responses):
            # Default response if none configured
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


@pytest.fixture
def temp_project_dir():
    """Create a temporary project directory for testing."""
    temp_dir = tempfile.mkdtemp(prefix="test_coding_agent_")
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_llm():
    """Create a mock LLM provider."""
    return MockLLMProvider()


@pytest.fixture
def coding_agent(temp_project_dir, mock_llm):
    """Create a CodingAgent instance for testing."""
    agent = CodingAgent(
        session_id="test-session",
        llm=mock_llm,
        project_directory=str(temp_project_dir)
    )
    return agent


class TestFileChangeTracking:
    """Test file change tracking functionality."""

    def test_record_file_change_creates_tracking_file(self, coding_agent, temp_project_dir):
        """Test that recording a file change creates the tracking file."""
        # Record a file change
        coding_agent._record_file_change("src/test.py")

        # Check that tracking file was created
        tracking_file = temp_project_dir / ".agent" / "review" / "files_modified.json"
        assert tracking_file.exists()

        # Verify contents
        with open(tracking_file, 'r') as f:
            data = json.load(f)

        assert data["session_id"] == "test-session"
        assert "session_start" in data
        assert data["files"] == ["src/test.py"]

    def test_record_file_change_handles_absolute_paths(self, coding_agent, temp_project_dir):
        """Test that absolute paths are converted to relative paths."""
        # Record with absolute path
        absolute_path = temp_project_dir / "src" / "test.py"
        coding_agent._record_file_change(str(absolute_path))

        # Verify it's stored as relative path
        tracked_files = coding_agent._get_tracked_file_changes()
        assert len(tracked_files) == 1
        assert not Path(tracked_files[0]).is_absolute()
        assert tracked_files[0] == "src/test.py" or tracked_files[0] == "src\\test.py"

    def test_record_file_change_avoids_duplicates(self, coding_agent):
        """Test that the same file is not tracked multiple times."""
        # Record same file twice
        coding_agent._record_file_change("src/test.py")
        coding_agent._record_file_change("src/test.py")

        # Should only have one entry
        tracked_files = coding_agent._get_tracked_file_changes()
        assert len(tracked_files) == 1
        assert tracked_files[0] == "src/test.py" or tracked_files[0] == "src\\test.py"

    def test_record_multiple_files(self, coding_agent):
        """Test recording multiple different files."""
        files = ["src/file1.py", "src/file2.py", "tests/test_file.py"]

        for file in files:
            coding_agent._record_file_change(file)

        tracked_files = coding_agent._get_tracked_file_changes()
        assert len(tracked_files) == 3

        # Normalize paths for comparison
        tracked_normalized = [f.replace("\\", "/") for f in tracked_files]
        for file in files:
            assert file in tracked_normalized

    def test_get_tracked_file_changes_empty(self, coding_agent):
        """Test getting tracked changes when none exist."""
        tracked_files = coding_agent._get_tracked_file_changes()
        assert tracked_files == []

    def test_record_file_change_handles_errors_gracefully(self, coding_agent, temp_project_dir):
        """Test that errors in recording don't crash the agent."""
        # Make the review directory read-only to cause an error
        review_dir = temp_project_dir / ".agent" / "review"
        review_dir.mkdir(parents=True, exist_ok=True)

        with patch('builtins.open', side_effect=PermissionError("Access denied")):
            # Should not raise, just log warning
            coding_agent._record_file_change("test.py")


class TestProcessToolCallsTracking:
    """Test that _process_tool_calls properly tracks file modifications."""

    def test_tracks_edit_tool_call(self, coding_agent):
        """Test that edit tool calls are tracked."""
        # Create mock LLM response with edit tool call
        mock_tool_call = Mock()
        mock_tool_call.name = "edit"
        mock_tool_call.id = "call_123"
        mock_tool_call.arguments = json.dumps({
            "file_path": "src/main.py",
            "old_string": "old",
            "new_string": "new"
        })

        mock_response = Mock()
        mock_response.tool_calls = [mock_tool_call]
        mock_response.content = "Editing file"

        # Process the tool calls
        coding_agent._process_tool_calls(mock_response)

        # Verify file was tracked
        tracked_files = coding_agent._get_tracked_file_changes()
        assert len(tracked_files) == 1
        assert "src/main.py" in tracked_files[0] or "src\\main.py" in tracked_files[0]

    def test_tracks_write_tool_call(self, coding_agent):
        """Test that write tool calls are tracked."""
        mock_tool_call = Mock()
        mock_tool_call.name = "write"
        mock_tool_call.id = "call_456"
        mock_tool_call.arguments = json.dumps({
            "file_path": "tests/test_new.py",
            "content": "print('test')"
        })

        mock_response = Mock()
        mock_response.tool_calls = [mock_tool_call]
        mock_response.content = "Writing file"

        coding_agent._process_tool_calls(mock_response)

        tracked_files = coding_agent._get_tracked_file_changes()
        assert len(tracked_files) == 1
        assert "tests/test_new.py" in tracked_files[0] or "tests\\test_new.py" in tracked_files[0]

    def test_tracks_multi_edit_tool_call(self, coding_agent):
        """Test that multi_edit tool calls track all files."""
        mock_tool_call = Mock()
        mock_tool_call.name = "multi_edit"
        mock_tool_call.id = "call_789"
        mock_tool_call.arguments = json.dumps({
            "edits": [
                {"file_path": "src/file1.py", "old_string": "a", "new_string": "b"},
                {"file_path": "src/file2.py", "old_string": "c", "new_string": "d"}
            ]
        })

        mock_response = Mock()
        mock_response.tool_calls = [mock_tool_call]
        mock_response.content = "Multi-editing files"

        coding_agent._process_tool_calls(mock_response)

        tracked_files = coding_agent._get_tracked_file_changes()
        assert len(tracked_files) == 2
        tracked_normalized = [f.replace("\\", "/") for f in tracked_files]
        assert "src/file1.py" in tracked_normalized
        assert "src/file2.py" in tracked_normalized

    def test_ignores_non_file_modification_tools(self, coding_agent):
        """Test that non-file-modification tools don't get tracked."""
        mock_tool_call = Mock()
        mock_tool_call.name = "bash"
        mock_tool_call.id = "call_999"
        mock_tool_call.arguments = json.dumps({"command": "ls -la"})

        mock_response = Mock()
        mock_response.tool_calls = [mock_tool_call]
        mock_response.content = "Running command"

        coding_agent._process_tool_calls(mock_response)

        # Should not track any files
        tracked_files = coding_agent._get_tracked_file_changes()
        assert tracked_files == []

    def test_tracks_mixed_tool_calls(self, coding_agent):
        """Test tracking when multiple tool types are called together."""
        # Create individual tool calls
        tc1 = Mock()
        tc1.name = "bash"
        tc1.id = "call_1"
        tc1.arguments = json.dumps({"command": "ls"})

        tc2 = Mock()
        tc2.name = "edit"
        tc2.id = "call_2"
        tc2.arguments = json.dumps({"file_path": "src/a.py", "old_string": "x", "new_string": "y"})

        tc3 = Mock()
        tc3.name = "read"
        tc3.id = "call_3"
        tc3.arguments = json.dumps({"file_path": "src/b.py"})

        tc4 = Mock()
        tc4.name = "write"
        tc4.id = "call_4"
        tc4.arguments = json.dumps({"file_path": "src/c.py", "content": "test"})

        mock_response = Mock()
        mock_response.tool_calls = [tc1, tc2, tc3, tc4]
        mock_response.content = "Multiple operations"

        coding_agent._process_tool_calls(mock_response)

        # Should only track edit and write
        tracked_files = coding_agent._get_tracked_file_changes()
        assert len(tracked_files) == 2
        tracked_normalized = [f.replace("\\", "/") for f in tracked_files]
        assert "src/a.py" in tracked_normalized
        assert "src/c.py" in tracked_normalized


class TestGatherPRContextWithTracking:
    """Test that _gather_pr_context uses tracked changes as fallback."""

    def test_uses_git_when_available(self, coding_agent, temp_project_dir):
        """Test that git is preferred when available."""
        # Initialize git repo and create a change
        import subprocess
        subprocess.run(["git", "init"], cwd=temp_project_dir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=temp_project_dir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=temp_project_dir, check=True, capture_output=True)

        # Create and stage a file
        test_file = temp_project_dir / "test.py"
        test_file.write_text("print('test')")
        subprocess.run(["git", "add", "test.py"], cwd=temp_project_dir, check=True, capture_output=True)

        # Also track a different file manually
        coding_agent._record_file_change("other.py")

        # Gather context
        context = coding_agent._gather_pr_context()

        # Should use git results (test.py), not tracked file (other.py)
        assert "files_changed" in context
        assert "test.py" in context["files_changed"]
        assert "other.py" not in context["files_changed"]

    def test_falls_back_to_tracked_when_git_unavailable(self, coding_agent, temp_project_dir):
        """Test that tracked changes are used when git is not available."""
        # Don't initialize git, just track files
        coding_agent._record_file_change("src/file1.py")
        coding_agent._record_file_change("src/file2.py")

        # Gather context
        context = coding_agent._gather_pr_context()

        # Should use tracked files
        assert "files_changed" in context
        assert len(context["files_changed"]) == 2
        tracked_normalized = [f.replace("\\", "/") for f in context["files_changed"]]
        assert "src/file1.py" in tracked_normalized
        assert "src/file2.py" in tracked_normalized

    def test_includes_original_request_and_todos(self, coding_agent, temp_project_dir):
        """Test that context includes all necessary information."""
        # Create draft PR description
        review_dir = temp_project_dir / ".agent" / "review"
        review_dir.mkdir(parents=True, exist_ok=True)
        draft_file = review_dir / "pr_description.draft.md"
        draft_file.write_text("""# PR Description (Draft)

## What was requested
Implement user authentication

## Implementation Progress
[Will be updated]
""")

        # Create todos
        todo_file = temp_project_dir / ".agent" / "todos.json"
        todo_file.write_text(json.dumps([
            {"content": "Add login endpoint", "status": "completed"},
            {"content": "Add logout endpoint", "status": "completed"},
            {"content": "Add tests", "status": "pending"}
        ]))

        # Track some files
        coding_agent._record_file_change("src/auth.py")

        # Gather context
        context = coding_agent._gather_pr_context()

        # Verify all parts
        assert context["original_request"] == "Implement user authentication"
        assert len(context["todos_completed"]) == 2
        assert "Add login endpoint" in context["todos_completed"]
        assert "Add logout endpoint" in context["todos_completed"]
        assert len(context["files_changed"]) == 1


class TestSessionInitialization:
    """Test that session start time is properly initialized."""

    def test_session_start_time_initialized(self, coding_agent):
        """Test that session_start_time is set during initialization."""
        assert hasattr(coding_agent, 'session_start_time')
        assert isinstance(coding_agent.session_start_time, datetime)

        # Should be recent (within last minute)
        now = datetime.now()
        delta = (now - coding_agent.session_start_time).total_seconds()
        assert delta < 60  # Less than 1 minute old


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_track_file_outside_project_directory(self, coding_agent, temp_project_dir):
        """Test tracking a file outside the project directory."""
        # Use an absolute path outside project
        outside_file = "/tmp/outside_project.py"
        coding_agent._record_file_change(outside_file)

        # Should still track it (as absolute path)
        tracked_files = coding_agent._get_tracked_file_changes()
        assert len(tracked_files) == 1
        assert outside_file in tracked_files[0]

    def test_malformed_tool_arguments(self, coding_agent):
        """Test handling of malformed tool arguments doesn't crash tracking."""
        mock_tool_call = Mock()
        mock_tool_call.name = "edit"
        mock_tool_call.id = "call_bad"
        mock_tool_call.arguments = "not valid json {{"

        mock_response = Mock()
        mock_response.tool_calls = [mock_tool_call]
        mock_response.content = "test"

        # The parent's _process_tool_calls will raise JSONDecodeError,
        # but our tracking code should handle the error gracefully before that
        # and log a warning without crashing during the tracking phase.
        # We expect the parent to raise the error.
        with pytest.raises(json.JSONDecodeError):
            coding_agent._process_tool_calls(mock_response)

        # Tracking should not have recorded any files due to malformed JSON
        tracked_files = coding_agent._get_tracked_file_changes()
        assert tracked_files == []

    def test_missing_file_path_in_arguments(self, coding_agent):
        """Test handling when file_path is missing from arguments."""
        mock_tool_call = Mock()
        mock_tool_call.name = "edit"
        mock_tool_call.id = "call_missing"
        mock_tool_call.arguments = json.dumps({"old_string": "a", "new_string": "b"})

        mock_response = Mock()
        mock_response.tool_calls = [mock_tool_call]
        mock_response.content = "test"

        # Should not crash
        coding_agent._process_tool_calls(mock_response)

        # Should not track any files
        tracked_files = coding_agent._get_tracked_file_changes()
        assert tracked_files == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
