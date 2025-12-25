"""
Utility commands for the CLI.
"""

import logging

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from agent_cli import __version__
from agent_cli.commands.router import CommandRouter
from agent_cli.session.manager import SessionManager

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


async def refine_prompt_command(*args: str, **context: object) -> None:
    """
    Create a PromptRefinerAgent session for interactive prompt refinement.

    This is a convenience command that creates a prompt refiner agent session
    to help improve your prompts through conversational analysis and refinement.

    Usage:
        /refine-prompt [initial-prompt]

    Args:
        *args: Command arguments (optional initial prompt to refine)
        **context: Context (expects 'session_manager' and 'repl_engine')

    Examples:
        /refine-prompt                           # Start refinement session, will ask for prompt
        /refine-prompt "Build a web app"         # Start with specific prompt to refine

    The prompt refiner agent will:
    - Analyze prompt quality across 5 dimensions (clarity, specificity, actionability, completeness, structure)
    - Ask natural follow-up questions to gather missing context
    - Iteratively refine until quality score >= 8.5
    - Save refined prompt to .archiflow/artifacts/refined_prompts/
    - Copy refined prompt to clipboard for easy use
    """
    # Get session manager from context
    session_manager = context.get("session_manager")
    if not isinstance(session_manager, SessionManager):
        console.print("[red]Error: Session manager not available[/red]")
        return

    # Get REPL engine from context (needed for subscribing to output)
    repl_engine = context.get("repl_engine")
    if repl_engine is None:
        console.print("[red]Error: REPL engine not available[/red]")
        return

    # Parse initial prompt (optional - join all args)
    initial_prompt = " ".join(args) if args else None

    # Create prompt refiner agent
    try:
        console.print("[bold magenta]✨ Starting Prompt Refinement Session[/bold magenta]\n")

        if initial_prompt:
            console.print(f"[dim]Initial prompt:[/dim] {initial_prompt[:80]}{'...' if len(initial_prompt) > 80 else ''}")
        else:
            console.print("[dim]Mode:[/dim] Interactive (will ask for your prompt)")

        console.print("[dim]Agent type:[/dim] PromptRefinerAgent")
        console.print()

        # Import factory function
        from agent_cli.agents.factory import create_agent

        # Create agent using factory
        agent = create_agent(agent_type="prompt_refiner", initial_prompt=initial_prompt)

        # Create session
        session = session_manager.create_session(agent=agent)

        # Subscribe to output (similar to main REPL loop)
        repl_engine.subscribe_to_output(session.session_id)

        # Display welcome message
        console.print(
            f"[green]✓[/green] Prompt Refiner agent session created\n"
            f"[dim]Session ID:[/dim] {session.session_id}\n"
        )

        console.print(
            "\n[bold magenta]🎯 What I'll do:[/bold magenta]\n"
            "The agent will help you refine your prompt through:\n"
            "  1. [dim]Analysis[/dim] - Quality scoring across 5 dimensions\n"
            "  2. [dim]Conversation[/dim] - Natural follow-up questions for missing context\n"
            "  3. [dim]Refinement[/dim] - Iterative improvement until quality >= 8.5\n"
            "  4. [dim]Storage[/dim] - Save to artifacts with full context\n"
            "  5. [dim]Clipboard[/dim] - Auto-copy for immediate use\n"
        )

        console.print(
            "\n[bold green]📊 Quality Dimensions:[/bold green]\n"
            "  • [yellow]Clarity[/yellow] - Is the goal clear and unambiguous?\n"
            "  • [yellow]Specificity[/yellow] - Are details and constraints specified?\n"
            "  • [yellow]Actionability[/yellow] - Can an agent act on it immediately?\n"
            "  • [yellow]Completeness[/yellow] - Is all necessary context included?\n"
            "  • [yellow]Structure[/yellow] - Is it well-organized and coherent?\n"
        )

        console.print(
            "\n[bold cyan]💾 Artifact Storage:[/bold cyan]\n"
            "  Refined prompts are saved to:\n"
            "  [yellow].archiflow/artifacts/refined_prompts/[/yellow]\n"
            "  Including metadata, analysis, conversation history, and clipboard copy.\n"
        )

        if initial_prompt:
            # Auto-start refinement with the provided prompt
            console.print("\n[dim]→ Starting prompt analysis...[/dim]\n")

            # Send initial prompt to agent
            success = session_manager.send_message(initial_prompt)

            # Clear agent_idle event to show spinner
            if success:
                repl_engine.agent_idle.clear()
        else:
            # Wait for user to provide their prompt
            console.print(
                "\n[cyan]Ready to refine! Please provide the prompt you'd like to improve.[/cyan]\n"
                "Examples:\n"
                "  • 'Help me build a website'\n"
                "  • 'Fix the bug in the login'\n"
                "  • 'Create a REST API'\n"
            )

    except Exception as e:
        from agent_cli.agents.factory import AgentFactoryError
        if isinstance(e, AgentFactoryError):
            console.print(f"[red]Error creating prompt refiner agent:[/red] {e}")
            console.print(
                "\n[yellow]Hint:[/yellow] Make sure you have set the OPENAI_API_KEY "
                "environment variable."
            )
        else:
            console.print(f"[red]Unexpected error:[/red] {e}")
            logger.exception("Failed to create prompt refiner agent")


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

    router.register(
        name="refine-prompt",
        handler=refine_prompt_command,
        description="Start interactive prompt refinement session (analyze and improve prompts)",
        usage="refine-prompt [initial-prompt]",
    )
