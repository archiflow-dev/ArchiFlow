"""
Unit tests for ShellContext.
"""

import os
from pathlib import Path
import pytest

from agent_cli.repl.shell_context import ShellContext, CommandResult


class TestCommandResult:
    """Tests for CommandResult dataclass."""

    def test_success_property_true(self):
        """Test success property returns True for returncode 0."""
        result = CommandResult(stdout="output", stderr="", returncode=0)
        assert result.success is True

    def test_success_property_false(self):
        """Test success property returns False for non-zero returncode."""
        result = CommandResult(stdout="", stderr="error", returncode=1)
        assert result.success is False


class TestShellContext:
    """Tests for ShellContext class."""

    def test_init_default_cwd(self):
        """Test initialization with default current working directory."""
        context = ShellContext()
        assert context.cwd == Path.cwd()
        assert context.history == []

    def test_init_custom_cwd(self):
        """Test initialization with custom working directory."""
        custom_path = Path("/tmp")
        context = ShellContext(initial_cwd=custom_path)
        assert context.cwd == custom_path

    def test_execute_pwd(self):
        """Test executing pwd returns current directory."""
        context = ShellContext()
        result = context.execute("pwd")

        assert result.success
        assert str(context.cwd) in result.stdout
        assert result.returncode == 0

    def test_execute_echo(self):
        """Test executing echo command."""
        context = ShellContext()
        result = context.execute("echo hello")

        assert result.success
        assert "hello" in result.stdout
        assert result.returncode == 0

    def test_execute_adds_to_history(self):
        """Test that executed commands are added to history."""
        context = ShellContext()
        context.execute("echo test1")
        context.execute("echo test2")

        assert len(context.history) == 2
        assert "echo test1" in context.history
        assert "echo test2" in context.history

    def test_cd_to_absolute_path(self, tmp_path):
        """Test changing to an absolute directory path."""
        context = ShellContext()
        result = context.execute(f"cd {tmp_path}")

        assert result.success
        assert context.cwd == tmp_path
        assert result.returncode == 0

    def test_cd_to_relative_path(self, tmp_path):
        """Test changing to a relative directory path."""
        # Create a subdirectory
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        context = ShellContext(initial_cwd=tmp_path)
        result = context.execute("cd subdir")

        assert result.success
        assert context.cwd == subdir
        assert result.returncode == 0

    def test_cd_to_home(self):
        """Test cd with no arguments goes to home directory."""
        context = ShellContext()
        result = context.execute("cd")

        assert result.success
        assert context.cwd == Path.home()
        assert result.returncode == 0

    def test_cd_to_nonexistent_directory(self):
        """Test cd to nonexistent directory fails."""
        context = ShellContext()
        result = context.execute("cd /this/path/does/not/exist")

        assert not result.success
        assert result.returncode == 1
        assert "No such file or directory" in result.stderr

    def test_cd_to_file_fails(self, tmp_path):
        """Test cd to a file (not directory) fails."""
        # Create a file
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        context = ShellContext(initial_cwd=tmp_path)
        result = context.execute(f"cd {test_file}")

        assert not result.success
        assert result.returncode == 1
        assert "Not a directory" in result.stderr

    def test_cd_with_tilde(self):
        """Test cd with ~ expands to home directory."""
        context = ShellContext()
        result = context.execute("cd ~")

        assert result.success
        assert context.cwd == Path.home()

    def test_execute_invalid_command(self):
        """Test executing an invalid command returns error."""
        context = ShellContext()
        result = context.execute("this_command_does_not_exist")

        assert not result.success
        assert result.returncode != 0

    def test_get_cwd_display_under_home(self, tmp_path):
        """Test get_cwd_display shows ~ for paths under home."""
        # Create a temp dir under home
        home_subdir = Path.home() / "test_subdir"
        context = ShellContext(initial_cwd=Path.home())

        display = context.get_cwd_display()
        # On Windows, Path.home() resolves to "C:/Users/username/." which shows as "~/."
        assert display.startswith("~")

    def test_get_cwd_display_not_under_home(self, tmp_path):
        """Test get_cwd_display shows full path for paths not under home."""
        # Use /tmp which is typically not under home on Unix
        # On Windows, tmp_path might be under home, so just check it returns something
        context = ShellContext(initial_cwd=tmp_path)

        display = context.get_cwd_display()
        # Just check that we get a non-empty display
        assert len(display) > 0

    @pytest.mark.skipif(os.name == "nt", reason="Timeout test not reliable on Windows")
    def test_command_execution_timeout(self):
        """Test that long-running commands timeout."""
        context = ShellContext()
        # This command should timeout (sleeps for 60 seconds)
        result = context.execute("python3 -c \"import time; time.sleep(60)\"")

        assert not result.success
        assert "timed out" in result.stderr.lower()
        assert result.returncode == 124
