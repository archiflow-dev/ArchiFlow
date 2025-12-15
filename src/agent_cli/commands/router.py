"""
Command router for parsing and dispatching slash commands.
"""

import shlex
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from rich.console import Console

console = Console()


@dataclass
class Command:
    """Represents a registered command."""

    name: str
    handler: Callable[..., Awaitable[None]]
    description: str
    usage: str | None = None


class CommandRouter:
    """
    Routes slash commands to their handlers.

    Handles command parsing, validation, and execution.
    """

    def __init__(self) -> None:
        """Initialize the command router."""
        self.commands: dict[str, Command] = {}

    def register(
        self,
        name: str,
        handler: Callable[..., Awaitable[None]],
        description: str,
        usage: str | None = None,
    ) -> None:
        """
        Register a command handler.

        Args:
            name: Command name (without the / prefix)
            handler: Async function to handle the command
            description: Short description of the command
            usage: Optional usage string
        """
        self.commands[name.lower()] = Command(
            name=name.lower(), handler=handler, description=description, usage=usage
        )

    def unregister(self, name: str) -> None:
        """
        Unregister a command.

        Args:
            name: Command name to unregister
        """
        self.commands.pop(name.lower(), None)

    def get_command(self, name: str) -> Command | None:
        """
        Get a registered command.

        Args:
            name: Command name

        Returns:
            Command object or None if not found
        """
        return self.commands.get(name.lower())

    def list_commands(self) -> list[Command]:
        """
        Get list of all registered commands.

        Returns:
            List of Command objects
        """
        return sorted(self.commands.values(), key=lambda c: c.name)

    def parse_command(self, input_text: str) -> tuple[str, list[str]] | None:
        """
        Parse a command string into name and arguments.

        Args:
            input_text: The input string (should start with /)

        Returns:
            Tuple of (command_name, args) or None if not a command
        """
        if not input_text.startswith("/"):
            return None

        # Remove the leading /
        command_text = input_text[1:].strip()

        if not command_text:
            return None

        try:
            # Use shlex to properly handle quoted arguments
            parts = shlex.split(command_text)
        except ValueError as e:
            # Handle unclosed quotes, etc.
            console.print(f"[red]Error parsing command:[/red] {e}")
            return None

        if not parts:
            return None

        command_name = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []

        return command_name, args

    async def execute(self, input_text: str, **context: Any) -> bool:
        """
        Parse and execute a command.

        Args:
            input_text: The command string (including /)
            **context: Additional context to pass to the handler

        Returns:
            True if command was executed, False if not a command or unknown
        """
        parsed = self.parse_command(input_text)

        if parsed is None:
            return False

        command_name, args = parsed

        # Look up the command
        command = self.get_command(command_name)

        if command is None:
            console.print(f"[red]Unknown command:[/red] /{command_name}")
            console.print("Type [bold]/help[/bold] to see available commands.")
            return False

        # Execute the command handler
        try:
            await command.handler(*args, **context)
            return True
        except TypeError as e:
            # Handle incorrect number of arguments
            console.print(f"[red]Error:[/red] {e}")
            if command.usage:
                console.print(f"[dim]Usage:[/dim] /{command.usage}")
            return False
        except Exception as e:
            console.print(f"[bold red]Command error:[/bold red] {e}")
            return False
