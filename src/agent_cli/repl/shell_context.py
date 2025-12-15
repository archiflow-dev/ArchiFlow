"""
Shell context manager for maintaining shell state across commands.
"""

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CommandResult:
    """Result of system command execution."""

    stdout: str
    stderr: str
    returncode: int

    @property
    def success(self) -> bool:
        """Whether the command executed successfully."""
        return self.returncode == 0


class ShellContext:
    """
    Maintains shell state across commands.

    This class manages the working directory and command history,
    allowing system commands to persist their state across the REPL session.
    """

    def __init__(self, initial_cwd: Path | None = None) -> None:
        """
        Initialize shell context.

        Args:
            initial_cwd: Initial working directory (defaults to current directory)
        """
        self.cwd = initial_cwd or Path.cwd()
        self.history: list[str] = []

    def execute(self, command: str) -> CommandResult:
        """
        Execute system command in the current context.

        Args:
            command: The shell command to execute

        Returns:
            CommandResult with stdout, stderr, and return code
        """
        # Handle cd specially (changes internal state)
        if command.strip().startswith("cd ") or command.strip() == "cd":
            return self._handle_cd(command)

        # Handle pwd specially (returns current directory)
        if command.strip() == "pwd":
            return CommandResult(stdout=str(self.cwd) + "\n", stderr="", returncode=0)

        # Execute command in self.cwd
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=str(self.cwd),
                capture_output=True,
                text=True,
                timeout=30,  # 30 second timeout
            )

            # Add to history
            self.history.append(command)

            return CommandResult(
                stdout=result.stdout, stderr=result.stderr, returncode=result.returncode
            )

        except subprocess.TimeoutExpired:
            return CommandResult(
                stdout="", stderr="Command timed out after 30 seconds", returncode=124
            )
        except Exception as e:
            return CommandResult(stdout="", stderr=f"Error: {e}", returncode=1)

    def _handle_cd(self, command: str) -> CommandResult:
        """
        Handle directory change command.

        Args:
            command: The cd command string

        Returns:
            CommandResult indicating success or failure
        """
        parts = command.strip().split(maxsplit=1)

        if len(parts) == 1:
            # cd with no args → home directory
            target = Path.home()
        else:
            target = Path(parts[1]).expanduser()

        # Make relative to current cwd if not absolute
        if not target.is_absolute():
            target = self.cwd / target

        # Resolve and validate
        try:
            target = target.resolve()

            if not target.exists():
                return CommandResult(
                    stdout="", stderr=f"cd: {target}: No such file or directory\n", returncode=1
                )

            if not target.is_dir():
                return CommandResult(
                    stdout="", stderr=f"cd: {target}: Not a directory\n", returncode=1
                )

            # Update internal state
            old_cwd = self.cwd
            self.cwd = target

            # Add to history
            self.history.append(command)

            return CommandResult(stdout="", stderr="", returncode=0)

        except Exception as e:
            return CommandResult(stdout="", stderr=f"cd: {e}\n", returncode=1)

    def get_cwd_display(self) -> str:
        """
        Get a user-friendly display string for the current working directory.

        Returns:
            Formatted current working directory (shortened if in home)
        """
        try:
            # Try to make path relative to home for cleaner display
            cwd_relative = self.cwd.relative_to(Path.home())
            return f"~/{cwd_relative}"
        except ValueError:
            # Not under home directory, use absolute path
            return str(self.cwd)
