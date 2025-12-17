"""
Utility commands for the CLI.
"""

import logging

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from agent_cli import __version__
from agent_cli.commands.router import CommandRouter

console = Console()
logger = logging.getLogger(__name__)


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


async def clear_history_command(**context: object) -> None:
    """
    Clear the current active session's agent history for a fresh start.

    Args:
        **context: Context passed from router (expects 'session_manager')
    """
    from agent_cli.session.manager import SessionManager

    session_manager = context.get("session_manager")
    if not isinstance(session_manager, SessionManager):
        console.print("[red]Error: Session manager not available[/red]")
        return

    # Get the active session
    active_session = session_manager.get_active_session()
    if not active_session:
        console.print("[yellow]No active session found. Create a session first with /new[/yellow]")
        return

    try:
        # Clear the agent's history
        if hasattr(active_session.agent, 'history'):
            # Check if it's a HistoryManager with clear method
            if hasattr(active_session.agent.history, 'clear'):
                active_session.agent.history.clear()
            else:
                # If no clear method, reinitialize the history
                from agent_framework.memory.history import HistoryManager
                from agent_framework.memory.summarizer import LLMSummarizer

                # Preserve the configuration
                old_history = active_session.agent.history
                active_session.agent.history = HistoryManager(
                    summarizer=LLMSummarizer(active_session.agent.llm),
                    model_config=active_session.agent.llm.model_config,
                    system_prompt_tokens=0,  # Will be recalculated
                    tools_tokens=0,  # Will be recalculated
                    retention_window=getattr(old_history, 'retention_window', 20)
                )

            console.print("[green]Success:[/green] Agent history cleared successfully. Ready for a fresh start!")
        else:
            console.print("[red]Error: Agent doesn't have a history to clear[/red]")
    except Exception as e:
        console.print(f"[red]Error clearing history: {e}[/red]")
        logger.exception("Failed to clear agent history")


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

    router.register(
        name="clear-history",
        handler=clear_history_command,
        description="Clear the current active session's agent history for a fresh start",
    )
