"""
System command handler for executing shell commands.
"""

import logging
import platform
from typing import TYPE_CHECKING
from rich.console import Console
from rich.table import Table

from agent_cli.repl.shell_context import ShellContext, CommandResult

if TYPE_CHECKING:
    from agent_cli.session.manager import SessionManager

console = Console()
logger = logging.getLogger(__name__)


class SystemCommandHandler:
    """
    Handles system command execution with auto-detection.

    This handler maintains a whitelist of common commands that should
    automatically execute as system commands without requiring a prefix.

    When directory changes (cd command), automatically syncs the active
    agent session's project_directory to match the shell working directory.
    """

    # Commands available on all platforms
    UNIVERSAL_COMMANDS = {
        "cd", "echo", "git", "python", "python3", "node",
        "pip", "npm", "yarn", "java", "ruby", "go"
    }

    # Unix/Linux/macOS specific commands
    UNIX_COMMANDS = {
        "pwd", "ls", "cat", "head", "tail", "touch", "cp", "mv",
        "mkdir", "rmdir", "rm", "grep", "find", "sed", "awk",
        "sort", "uniq", "wc", "diff", "file", "stat",
        "whoami", "hostname", "uname", "date", "uptime",
        "ps", "top", "kill", "killall",
        "curl", "wget", "ssh", "scp", "rsync",
        "tar", "gzip", "gunzip", "zip", "unzip",
        "tree", "which", "man", "clear", "env", "export",
        "chmod", "chown", "ln", "df", "du"
    }

    # Windows specific commands
    WINDOWS_COMMANDS = {
        "dir", "type", "copy", "xcopy", "move", "del", "erase",
        "md", "mkdir", "rd", "rmdir", "cls", "clear",
        "findstr", "where", "set", "path",
        "tasklist", "taskkill", "systeminfo",
        "ipconfig", "ping", "netstat", "tracert",
        "powershell", "cmd", "tree",
        "attrib", "comp", "fc", "more"
    }

    # Cross-platform development tools
    DEV_TOOLS = {
        "git", "svn", "hg",
        "pip", "pip3", "conda",
        "npm", "yarn", "pnpm", "npx",
        "cargo", "rustc",
        "gem", "bundle",
        "mvn", "gradle", "ant",
        "make", "cmake", "ninja",
        "docker", "docker-compose", "kubectl",
        "terraform", "ansible"
    }

    @classmethod
    def get_available_commands(cls) -> set[str]:
        """Get all commands available on current platform."""
        commands = cls.UNIVERSAL_COMMANDS.copy()
        commands.update(cls.DEV_TOOLS)

        if platform.system() == "Windows":
            commands.update(cls.WINDOWS_COMMANDS)
        else:  # Unix-like (Linux, macOS, etc.)
            commands.update(cls.UNIX_COMMANDS)

        return commands

    # Commands that require user confirmation (dangerous operations)
    DANGEROUS_COMMANDS = {
        "rm -rf",
        "rm -r",
        "rm -fr",
        "del /f",
        "del /s",
        "format",
        "mkfs",
        "dd if=",
        "shutdown",
        "reboot",
        "halt",
        "poweroff",
        "init 0",
        "init 6",
        "systemctl poweroff",
        "systemctl reboot",
    }

    def __init__(
        self,
        shell_context: ShellContext,
        session_manager: "SessionManager | None" = None
    ) -> None:
        """
        Initialize system command handler.

        Args:
            shell_context: The shell context for maintaining state
            session_manager: Optional session manager for agent sync
        """
        self.context = shell_context
        self.session_manager = session_manager

    def is_system_command(self, input_text: str) -> bool:
        """
        Detect if input is a system command based on whitelist.

        Args:
            input_text: The user input to analyze

        Returns:
            True if input should be executed as a system command
        """
        # Empty input
        if not input_text.strip():
            return False

        # Already handled by CLI (starts with /)
        if input_text.startswith("/"):
            return False

        # Check if first word is in whitelist
        first_word = input_text.strip().split()[0].lower()
        return first_word in self.get_available_commands()

    def is_dangerous(self, command: str) -> bool:
        """
        Check if command is potentially dangerous.

        Args:
            command: The command string to check

        Returns:
            True if command is dangerous and requires confirmation
        """
        cmd_lower = command.lower().strip()

        # Check for exact matches or substring matches
        for danger in self.DANGEROUS_COMMANDS:
            if danger in cmd_lower:
                return True

        return False

    async def execute(self, command: str, require_confirmation: bool = True) -> CommandResult:
        """
        Execute system command with proper output handling.

        Args:
            command: The command to execute
            require_confirmation: Whether to require confirmation for dangerous commands

        Returns:
            CommandResult with execution details
        """
        # Safety check for dangerous commands
        if require_confirmation and self.is_dangerous(command):
            console.print(f"\n[yellow]⚠️  Potentially dangerous command:[/yellow] {command}")
            console.print("[yellow]This command could delete files or cause system changes.[/yellow]")

            # For now, we'll just warn and block
            # TODO: Implement proper confirmation prompt
            console.print("[red]Command blocked for safety.[/red]")
            console.print("[dim]Use /exec to force execution (coming soon)[/dim]\n")

            return CommandResult(stdout="", stderr="Command blocked for safety\n", returncode=1)

        # Execute the command
        logger.debug(f"Executing system command: {command}")

        try:
            result = self.context.execute(command)

            # Sync agent directory if cd succeeded
            if command.strip().startswith("cd") and result.success:
                self._sync_agent_directory()

            # Display output
            if result.stdout:
                console.print(result.stdout, end="")

            if result.stderr:
                console.print(f"[red]{result.stderr}[/red]", end="")

            return result

        except Exception as e:
            error_msg = f"Error executing command: {e}\n"
            console.print(f"[red]{error_msg}[/red]")
            logger.error(error_msg)
            return CommandResult(stdout="", stderr=error_msg, returncode=1)

    def _sync_agent_directory(self) -> None:
        """
        Sync active agent's project_directory to shell working directory.

        When cd changes the shell directory, this updates the agent's:
        - project_directory attribute
        - execution_context.working_directory
        - All tools' execution_context.working_directory

        The system prompt is automatically formatted with the new directory
        on the next agent step (no history manipulation needed).
        """
        if not self.session_manager:
            return

        session = self.session_manager.get_active_session()
        if not session:
            return

        agent = session.agent

        # Check if agent has project_directory attribute
        if not hasattr(agent, 'project_directory'):
            return

        old_dir = agent.project_directory
        new_dir = self.context.cwd

        # No change needed
        if old_dir == new_dir:
            return

        # 1. Update agent's project directory
        agent.project_directory = new_dir

        # 2. Update execution context
        if hasattr(agent, 'execution_context') and agent.execution_context is not None:
            agent.execution_context.working_directory = str(new_dir)

        # 3. Update all tools' execution contexts
        if hasattr(agent, 'tools'):
            for tool in agent.tools.list_tools():
                if hasattr(tool, 'execution_context') and tool.execution_context is not None:
                    tool.execution_context.working_directory = str(new_dir)

        # 4. Notify user
        console.print(f"[dim]→ Agent working directory: {new_dir}[/dim]")

        logger.info(f"Synced agent directory: {old_dir} → {new_dir}")

    @classmethod
    def display_available_commands(cls):
        """Display all available shell commands for the current platform."""
        current_platform = platform.system()

        # Create header
        console.print(f"\n[bold cyan]Available Shell Commands[/bold cyan] ({current_platform})\n")

        # Create table
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Category", style="cyan", width=20)
        table.add_column("Commands", style="white")

        # Universal commands
        universal = sorted(cls.UNIVERSAL_COMMANDS)
        table.add_row(
            "Universal",
            ", ".join(universal)
        )

        # Platform-specific
        if current_platform == "Windows":
            windows_cmds = sorted(cls.WINDOWS_COMMANDS)
            table.add_row(
                "Windows",
                ", ".join(windows_cmds)
            )
        else:
            unix_cmds = sorted(cls.UNIX_COMMANDS)
            table.add_row(
                "Unix/Linux",
                ", ".join(unix_cmds)
            )

        # Development tools
        dev_tools = sorted(cls.DEV_TOOLS)
        table.add_row(
            "Development Tools",
            ", ".join(dev_tools)
        )

        console.print(table)

        # Show total count
        total = len(cls.get_available_commands())
        console.print(f"\n[dim]Total: {total} commands available on this system[/dim]")
        console.print(f"[dim]Type any command directly (no prefix needed)[/dim]\n")
