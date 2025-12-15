"""
Utility commands for the CLI.
"""

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from agent_cli import __version__
from agent_cli.commands.router import CommandRouter

console = Console()


async def help_command(**context: object) -> None:
    """
    Show available commands.

    Args:
        **context: Context passed from router (expects 'router')
    """
    router = context.get("router")
    if not isinstance(router, CommandRouter):
        console.print("[red]Error: Router not available[/red]")
        return

    commands = router.list_commands()

    help_text = "# Available Commands\n\n"

    for cmd in commands:
        help_text += f"- `/{cmd.name}` - {cmd.description}\n"
        if cmd.usage:
            help_text += f"  - Usage: `/{cmd.usage}`\n"

    help_text += "\n**More commands coming soon!**"

    console.print(Panel(Markdown(help_text.strip()), title="Help", border_style="blue"))
    console.print()


async def exit_command(**context: object) -> None:
    """
    Exit the REPL.

    Args:
        **context: Context passed from router (expects 'repl_engine')
    """
    from agent_cli.repl.engine import REPLEngine

    repl_engine = context.get("repl_engine")
    if not isinstance(repl_engine, REPLEngine):
        console.print("[red]Error: REPL engine not available[/red]")
        return

    console.print("[cyan]Goodbye![/cyan]")
    repl_engine.running = False


async def clear_command(**context: object) -> None:
    """
    Clear the screen.

    Args:
        **context: Context passed from router (unused)
    """
    console.clear()


async def version_command(**context: object) -> None:
    """
    Show version information.

    Args:
        **context: Context passed from router (unused)
    """
    console.print(
        f"[bold orange1]X Agent CLI[/bold orange1] version [green]{__version__}[/green]"
    )


async def shell_commands_command(**context: object) -> None:
    """
    Show available shell commands for current platform.

    Args:
        **context: Context passed from router (unused)
    """
    from agent_cli.commands.system import SystemCommandHandler

    SystemCommandHandler.display_available_commands()


def register_utility_commands(router: CommandRouter) -> None:
    """
    Register all utility commands with the router.

    Args:
        router: The command router to register commands with
    """
    router.register(
        name="help",
        handler=help_command,
        description="Show this help message",
    )

    router.register(
        name="exit",
        handler=exit_command,
        description="Exit the REPL",
    )

    router.register(
        name="quit",
        handler=exit_command,
        description="Exit the REPL (alias for /exit)",
    )

    router.register(
        name="clear",
        handler=clear_command,
        description="Clear the screen",
    )

    router.register(
        name="version",
        handler=version_command,
        description="Show version information",
    )

    router.register(
        name="shell-commands",
        handler=shell_commands_command,
        description="Show available shell commands for current platform",
    )
