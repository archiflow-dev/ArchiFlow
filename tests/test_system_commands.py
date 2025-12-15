"""
Unit tests for SystemCommandHandler.
"""

from pathlib import Path
import platform
import pytest

from agent_cli.commands.system import SystemCommandHandler
from agent_cli.repl.shell_context import ShellContext


class TestSystemCommandHandler:
    """Tests for SystemCommandHandler class."""

    def test_init(self):
        """Test initialization of SystemCommandHandler."""
        context = ShellContext()
        handler = SystemCommandHandler(context)

        assert handler.context == context
        commands = handler.get_available_commands()
        assert isinstance(commands, set)
        assert len(commands) > 0

    def test_is_system_command_whitelist_match(self):
        """Test is_system_command returns True for whitelisted commands."""
        context = ShellContext()
        handler = SystemCommandHandler(context)

        # Test universal commands (available on all platforms)
        assert handler.is_system_command("cd src") is True
        assert handler.is_system_command("git status") is True
        assert handler.is_system_command("echo hello") is True
        assert handler.is_system_command("python --version") is True

        # Test platform-specific commands
        if platform.system() == "Windows":
            assert handler.is_system_command("dir") is True
            assert handler.is_system_command("cls") is True
        else:
            assert handler.is_system_command("ls") is True
            assert handler.is_system_command("ls -la") is True
            assert handler.is_system_command("pwd") is True

    def test_is_system_command_not_whitelisted(self):
        """Test is_system_command returns False for non-whitelisted input."""
        context = ShellContext()
        handler = SystemCommandHandler(context)

        # These should not be detected as system commands
        assert handler.is_system_command("review this code") is False
        assert handler.is_system_command("explain the function") is False
        assert handler.is_system_command("help me with this") is False

    def test_is_system_command_cli_command(self):
        """Test is_system_command returns False for CLI commands (starting with /)."""
        context = ShellContext()
        handler = SystemCommandHandler(context)

        assert handler.is_system_command("/help") is False
        assert handler.is_system_command("/new") is False
        assert handler.is_system_command("/exit") is False

    def test_is_system_command_empty_input(self):
        """Test is_system_command returns False for empty input."""
        context = ShellContext()
        handler = SystemCommandHandler(context)

        assert handler.is_system_command("") is False
        assert handler.is_system_command("   ") is False

    def test_is_system_command_case_insensitive(self):
        """Test is_system_command is case-insensitive."""
        context = ShellContext()
        handler = SystemCommandHandler(context)

        # Test with universal commands
        assert handler.is_system_command("CD") is True
        assert handler.is_system_command("GIT") is True
        assert handler.is_system_command("Echo") is True

        # Test with platform-specific commands
        if platform.system() == "Windows":
            assert handler.is_system_command("DIR") is True
        else:
            assert handler.is_system_command("LS") is True
            assert handler.is_system_command("Ls") is True
            assert handler.is_system_command("PWD") is True

    def test_is_dangerous_rm_commands(self):
        """Test is_dangerous detects dangerous rm commands."""
        context = ShellContext()
        handler = SystemCommandHandler(context)

        assert handler.is_dangerous("rm -rf /") is True
        assert handler.is_dangerous("rm -rf *") is True
        assert handler.is_dangerous("rm -r somedir") is True
        assert handler.is_dangerous("rm file.txt") is False  # Not recursive

    def test_is_dangerous_format_commands(self):
        """Test is_dangerous detects format commands."""
        context = ShellContext()
        handler = SystemCommandHandler(context)

        assert handler.is_dangerous("format c:") is True
        assert handler.is_dangerous("mkfs /dev/sda") is True

    def test_is_dangerous_shutdown_commands(self):
        """Test is_dangerous detects shutdown commands."""
        context = ShellContext()
        handler = SystemCommandHandler(context)

        assert handler.is_dangerous("shutdown now") is True
        assert handler.is_dangerous("reboot") is True
        assert handler.is_dangerous("halt") is True
        assert handler.is_dangerous("systemctl poweroff") is True

    def test_is_dangerous_case_insensitive(self):
        """Test is_dangerous is case-insensitive."""
        context = ShellContext()
        handler = SystemCommandHandler(context)

        assert handler.is_dangerous("RM -RF /") is True
        assert handler.is_dangerous("SHUTDOWN") is True

    def test_is_dangerous_safe_commands(self):
        """Test is_dangerous returns False for safe commands."""
        context = ShellContext()
        handler = SystemCommandHandler(context)

        assert handler.is_dangerous("ls -la") is False
        assert handler.is_dangerous("cat file.txt") is False
        assert handler.is_dangerous("echo hello") is False
        assert handler.is_dangerous("git status") is False

    @pytest.mark.asyncio
    async def test_execute_safe_command(self):
        """Test execute runs safe commands successfully."""
        context = ShellContext()
        handler = SystemCommandHandler(context)

        result = await handler.execute("echo test", require_confirmation=False)

        assert result.success
        assert "test" in result.stdout

    @pytest.mark.asyncio
    async def test_execute_dangerous_command_blocked(self):
        """Test execute blocks dangerous commands when confirmation required."""
        context = ShellContext()
        handler = SystemCommandHandler(context)

        result = await handler.execute("rm -rf /", require_confirmation=True)

        assert not result.success
        assert "blocked for safety" in result.stderr.lower()
        assert result.returncode == 1

    @pytest.mark.asyncio
    async def test_execute_pwd(self):
        """Test execute handles pwd command."""
        context = ShellContext()
        handler = SystemCommandHandler(context)

        result = await handler.execute("pwd", require_confirmation=False)

        assert result.success
        assert str(context.cwd) in result.stdout

    @pytest.mark.asyncio
    async def test_execute_cd(self, tmp_path):
        """Test execute handles cd command and updates context."""
        context = ShellContext()
        handler = SystemCommandHandler(context)

        result = await handler.execute(f"cd {tmp_path}", require_confirmation=False)

        assert result.success
        assert context.cwd == tmp_path

    def test_whitelist_contains_common_commands(self):
        """Test that whitelist contains expected common commands."""
        context = ShellContext()
        handler = SystemCommandHandler(context)
        commands = handler.get_available_commands()

        # Test universal commands that should always be present
        universal_commands = ["cd", "echo", "git", "python", "node", "npm", "pip"]
        for cmd in universal_commands:
            assert cmd in commands, f"{cmd} should be in whitelist"

        # Test platform-specific commands
        if platform.system() == "Windows":
            windows_commands = ["dir", "cls", "type"]
            for cmd in windows_commands:
                assert cmd in commands, f"{cmd} should be in Windows whitelist"
        else:
            unix_commands = ["ls", "pwd", "cat", "mkdir", "grep", "find"]
            for cmd in unix_commands:
                assert cmd in commands, f"{cmd} should be in Unix whitelist"

    def test_whitelist_count(self):
        """Test that whitelist has reasonable number of commands."""
        context = ShellContext()
        handler = SystemCommandHandler(context)
        commands = handler.get_available_commands()

        # Should have a good set of commands (at least 30)
        # Windows has ~72 commands, Unix has ~92 commands
        assert len(commands) >= 30
