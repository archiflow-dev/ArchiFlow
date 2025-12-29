"""
Utility commands for the CLI.
"""

import json
import logging
from pathlib import Path

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
            f"[green]OK[/green] Prompt Refiner agent session created\n"
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


async def init_command(**context: object) -> None:
    """
    Initialize .archiflow directory structure.

    Creates:
    - .archiflow/ directory
    - .archiflow/tools/ subdirectory
    - .archiflow/.gitignore (with *.local.* pattern)
    - .archiflow/settings.json (with default settings)
    - .archiflow/ARCHIFLOW.md (with template)

    Args:
        **context: Context passed from router (unused)
    """
    working_dir = Path.cwd()
    archiflow_dir = working_dir / ".archiflow"

    if archiflow_dir.exists():
        console.print(
            f"[yellow].archiflow directory already exists at {archiflow_dir}[/yellow]"
        )
        console.print("[dim]Use /config to view or edit settings[/dim]")
        return

    try:
        # Create directory
        archiflow_dir.mkdir()

        # Create subdirectories
        (archiflow_dir / "tools").mkdir()

        # Create .gitignore
        (archiflow_dir / ".gitignore").write_text("*.local.*\n")

        # Create example settings.json
        settings = {
            "agent": {
                "defaultModel": "claude-sonnet-4-5-20250929"
            },
            "autoRefinement": {
                "enabled": False,
                "threshold": 8.0,
                "minLength": 10
            }
        }
        settings_path = archiflow_dir / "settings.json"
        settings_path.write_text(json.dumps(settings, indent=2))

        # Create ARCHIFLOW.md template
        archiflow_md = f"""# ArchiFlow Configuration for {working_dir.name}

## Project Overview
[Brief description of this project]

## Tech Stack
- Languages:
- Frameworks:
- Databases:

## Coding Standards
- Style guide:
- Linting:
- Testing:

## Agent Preferences
[Specific behaviors for agents]
"""
        (archiflow_dir / "ARCHIFLOW.md").write_text(archiflow_md)

        console.print(f"[green]OK[/green] Initialized .archiflow at {archiflow_dir}")
        console.print("  [dim]Created files:[/dim]")
        console.print("    [cyan]-[/cyan] settings.json: Project configuration")
        console.print("    [cyan]-[/cyan] ARCHIFLOW.md: Project context and instructions")
        console.print("    [cyan]-[/cyan] tools/: Tool-specific configurations")
        console.print("    [cyan]-[/cyan] .gitignore: Excludes *.local.* files")
        console.print()
        console.print("[dim]Next steps:[/dim]")
        console.print("  • Use [bold]/config[/bold] to view or edit settings")
        console.print("  • Edit [bold]ARCHIFLOW.md[/bold] to add project-specific context")
        console.print("  • Add tool configs under [bold]tools/[/bold] directory")

    except Exception as e:
        console.print(f"[red]Error initializing .archiflow:[/red] {e}")
        logger.exception("Failed to initialize .archiflow directory")


async def config_command(key: str = None, value: str = None, global_flag: bool = False, **context: object) -> None:
    """
    View or edit configuration settings.

    Usage:
        /config                    # Show all settings
        /config agent               # Show specific key
        /config agent.model         # Show nested key
        /config autoRefinement.enabled true    # Set value
        /config -g autoRefinement.enabled true    # Set global config

    Args:
        **context: Context passed from router (unused)
    """
    if global_flag:
        config_path = Path.home() / ".archiflow" / "settings.json"
        config_type = "global"
    else:
        config_path = Path.cwd() / ".archiflow" / "settings.json"
        config_type = "project"

    if not config_path.exists():
        console.print(f"[yellow]No {config_type} configuration found at {config_path}[/yellow]")
        console.print("[dim]Run /init to create configuration[/dim]")
        return

    try:
        # Load config
        settings = json.loads(config_path.read_text())

        if key is None:
            # Show all settings
            console.print(f"[bold]{config_type.title()} Configuration:[/bold] {config_path}")
            console.print()
            console.print_json(settings)

        elif value is None:
            # Show specific key
            keys = key.split(".")
            result = settings
            for k in keys:
                if isinstance(result, dict):
                    result = result.get(k, {})
                else:
                    result = {}
                    console.print(f"[red]Key '{key}' not found in configuration[/red]")
                    return

            console.print(f"[bold]{config_type.title()} Configuration[/bold] -> [cyan]{key}[/cyan]:")
            console.print()
            console.print_json(result)

        else:
            # Set key
            keys = key.split(".")
            target = settings
            for k in keys[:-1]:
                if k not in target:
                    target[k] = {}
                target = target[k]

            # Try to parse value as JSON first, then use as string
            try:
                parsed_value = json.loads(value)
            except json.JSONDecodeError:
                parsed_value = value

            target[keys[-1]] = parsed_value

            # Write back
            config_path.write_text(json.dumps(settings, indent=2))
            console.print(f"[green]OK[/green] Set {config_type}.{key} = {parsed_value}")

    except json.JSONDecodeError as e:
        console.print(f"[red]Error parsing configuration:[/red] {e}")
        console.print(f"[dim]File: {config_path}[/dim]")
    except Exception as e:
        console.print(f"[red]Error accessing configuration:[/red] {e}")
        logger.exception("Failed to access configuration")


async def auto_refine_command(*args: str, **context: object) -> None:
    """
    Toggle automatic prompt refinement for the current session.

    This command allows you to enable or disable auto-refinement during
    an active session, overriding the .env or ARCHIFLOW.md settings.

    Usage:
        /auto-refine           # Show current status
        /auto-refine on        # Enable auto-refinement
        /auto-refine off       # Disable auto-refinement
        /auto-refine toggle    # Toggle current state

    Args:
        *args: Command arguments (on|off|toggle|status)
        **context: Context passed from router (expects 'session_manager')

    Examples:
        /auto-refine           # Check if it's enabled or disabled
        /auto-refine on        # Enable for this session
        /auto-refine off       # Disable for this session
        /auto-refine toggle    # Switch between on/off
    """
    # Get session manager from context
    session_manager = context.get("session_manager")
    if not isinstance(session_manager, SessionManager):
        console.print("[red]Error: Session manager not available[/red]")
        return

    # Get active session
    active_session = session_manager.get_active_session()
    if not active_session:
        console.print("[yellow]No active session. Create a session first with /new[/yellow]")
        return

    # Parse action (default to 'status')
    action = args[0].lower() if args else "status"

    if action not in ["on", "off", "toggle", "status"]:
        console.print(f"[red]Error: Invalid action '{action}'[/red]")
        console.print("[dim]Usage: /auto-refine [on|off|toggle|status][/dim]")
        return

    # Get current state
    current_state = active_session.config.auto_refine_prompts

    # Execute action
    if action == "on":
        active_session.config.auto_refine_prompts = True
        new_state = True
        action_msg = "enabled"
    elif action == "off":
        active_session.config.auto_refine_prompts = False
        new_state = False
        action_msg = "disabled"
    elif action == "toggle":
        new_state = active_session.config.toggle_auto_refine()
        action_msg = "enabled" if new_state else "disabled"
    else:  # status
        new_state = current_state
        action_msg = None

    # Display result
    if action_msg:
        status_emoji = "✅" if new_state else "❌"
        console.print(f"\n{status_emoji} [bold]Auto-refinement {action_msg}[/bold] for this session")

        if new_state:
            console.print("\n[dim]Prompts will be automatically analyzed and refined before reaching the agent.[/dim]")
            console.print("[yellow]⚠️  Warning: This DOUBLES cost and latency of every interaction.[/yellow]")
        else:
            console.print("\n[dim]Prompts will be sent to the agent without refinement.[/dim]")
            console.print("[green]Use /refine-prompt to manually refine a specific prompt.[/green]")
    else:
        # Status query
        status_emoji = "✅ ON" if current_state else "❌ OFF"
        console.print(f"\n[bold]Auto-refinement status:[/bold] {status_emoji}")

        if current_state:
            console.print("[dim]Prompts are being automatically refined.[/dim]")
            console.print("[yellow]⚠️  Doubling cost and latency on every interaction.[/yellow]")
        else:
            console.print("[dim]Prompts are sent without automatic refinement.[/dim]")

        console.print("\n[dim]Use /auto-refine [on|off|toggle] to change.[/dim]")

    console.print()


async def setup_font_command(*args: str, **context: object) -> None:
    """
    Setup terminal font configuration for VS Code.

    This command:
    1. Loads font preferences from .archiflow/config/terminal.yaml
    2. Checks if preferred font is installed
    3. Generates .vscode/settings.json with font configuration
    4. Provides installation instructions if font not found

    Usage:
        /setup-font                    # Use config from terminal.yaml
        /setup-font "Cascadia Code"    # Override preferred font
        /setup-font --check            # Check installed fonts only
        /setup-font --list             # List all installed fonts

    Args:
        *args: Command arguments (font name or flags)
        **context: Context passed from router (unused)
    """
    from agent_cli.config.terminal_config import load_terminal_config, save_terminal_config, TerminalConfig
    from agent_cli.utils.font_detection import FontDetector

    working_dir = Path.cwd()

    # Parse arguments
    if args and args[0] == "--check":
        # Check mode: validate current configuration
        console.print("\n[bold cyan]Checking Font Installation[/bold cyan]\n")

        config = load_terminal_config(working_dir)
        recommended = FontDetector.get_recommended_fonts()

        console.print(f"[bold]Preferred Font:[/bold] {config.preferred_font}")
        is_installed = FontDetector.is_font_installed(config.preferred_font)
        status = "[green]✓ Installed[/green]" if is_installed else "[red]✗ Not Found[/red]"
        console.print(f"  Status: {status}\n")

        console.print("[bold]Fallback Fonts:[/bold]")
        for font in config.fallback_fonts:
            is_installed = FontDetector.is_font_installed(font)
            status = "[green]✓[/green]" if is_installed else "[red]✗[/red]"
            console.print(f"  {status} {font}")

        console.print("\n[bold]Recommended Developer Fonts:[/bold]")
        for font_name, info in recommended.items():
            installed = "[green]✓ Installed[/green]" if info["installed"] else "[red]✗ Not Installed[/red]"
            ligatures = "[dim](ligatures)[/dim]" if info["ligatures"] else ""
            console.print(f"  {installed} {font_name} {ligatures}")
            console.print(f"    [dim]{info['description']}[/dim]")
            if not info["installed"] and info["download"] != "Pre-installed on Windows":
                console.print(f"    [cyan]Download:[/cyan] {info['download']}")

        console.print()
        return

    elif args and args[0] == "--list":
        # List all installed fonts
        console.print("\n[bold cyan]Scanning Installed Fonts...[/bold cyan]\n")
        fonts = FontDetector.get_installed_fonts()

        if fonts:
            console.print(f"[green]Found {len(fonts)} fonts:[/green]\n")
            # Show first 50, then summarize
            for i, font in enumerate(fonts[:50]):
                console.print(f"  • {font}")
            if len(fonts) > 50:
                console.print(f"\n  [dim]... and {len(fonts) - 50} more fonts[/dim]")
        else:
            console.print("[yellow]Could not enumerate installed fonts[/yellow]")
            console.print("[dim]Font detection may vary by platform[/dim]")

        console.print()
        return

    # Load configuration
    config = load_terminal_config(working_dir)

    # Override preferred font if provided
    if args and not args[0].startswith("--"):
        font_name = " ".join(args)
        config.preferred_font = font_name
        console.print(f"\n[cyan]Using custom font:[/cyan] {font_name}\n")

    # Check if preferred font is installed
    console.print(f"[bold]Checking font installation:[/bold] {config.preferred_font}")
    is_installed = FontDetector.is_font_installed(config.preferred_font)

    if is_installed:
        console.print(f"  [green]✓ {config.preferred_font} is installed[/green]\n")
    else:
        console.print(f"  [red]✗ {config.preferred_font} not found[/red]\n")

        # Show installation instructions
        recommended = FontDetector.get_recommended_fonts()
        if config.preferred_font in recommended:
            info = recommended[config.preferred_font]
            console.print(f"[bold yellow]Installation Instructions:[/bold yellow]")
            console.print(f"  [cyan]Download:[/cyan] {info['download']}")
            console.print(f"  [dim]{info['description']}[/dim]\n")

        # Check if any fallback is installed
        fallback_found = None
        for fallback in config.fallback_fonts:
            if FontDetector.is_font_installed(fallback):
                fallback_found = fallback
                break

        if fallback_found:
            console.print(f"[green]✓ Fallback font found:[/green] {fallback_found}")
            console.print(f"  [dim]VS Code will use this until {config.preferred_font} is installed[/dim]\n")

    # Generate VS Code settings
    vscode_dir = working_dir / ".vscode"
    settings_path = vscode_dir / "settings.json"

    # Load existing settings or create new
    if settings_path.exists():
        try:
            existing_settings = json.loads(settings_path.read_text(encoding="utf-8"))
            console.print(f"[cyan]Found existing VS Code settings:[/cyan] {settings_path}")
        except json.JSONDecodeError:
            existing_settings = {}
            console.print(f"[yellow]Could not parse existing settings, will create new[/yellow]")
    else:
        existing_settings = {}
        console.print(f"[cyan]Creating new VS Code settings:[/cyan] {settings_path}")

    # Merge font settings
    font_settings = config.to_vscode_settings()
    merged_settings = {**existing_settings, **font_settings}

    # Create .vscode directory if needed
    vscode_dir.mkdir(exist_ok=True)

    # Write settings
    try:
        settings_path.write_text(
            json.dumps(merged_settings, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        console.print(f"[green]✓ VS Code settings updated:[/green] {settings_path}\n")
    except Exception as e:
        console.print(f"[red]Error writing settings:[/red] {e}\n")
        return

    # Display what was configured
    console.print("[bold]Font Configuration:[/bold]")
    console.print(f"  [cyan]Font Family:[/cyan] {config.font_family}")
    console.print(f"  [cyan]Font Size:[/cyan] {config.font_size}")
    console.print(f"  [cyan]Ligatures:[/cyan] {'Enabled' if config.enable_ligatures else 'Disabled'}")
    console.print(f"  [cyan]Line Height:[/cyan] {config.line_height}")
    console.print()

    # Next steps
    console.print("[bold green]Next Steps:[/bold green]")
    if not is_installed:
        console.print("  1. Install the preferred font (see download link above)")
        console.print("  2. Restart VS Code")
        console.print("  3. Open terminal and run: python run_dev.py")
    else:
        console.print("  1. Restart VS Code (or reload window)")
        console.print("  2. Open terminal and run: python run_dev.py")
        console.print("  3. You should see monospaced developer font!")

    console.print()
    console.print("[dim]Tip: Use /setup-font --check to verify font installation anytime[/dim]")
    console.print()


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

    router.register(
        name="init",
        handler=init_command,
        description="Initialize .archiflow directory structure",
    )

    router.register(
        name="config",
        handler=config_command,
        description="View or edit configuration settings",
        usage="config [key] [value] [-g]",
    )

    router.register(
        name="auto-refine",
        handler=auto_refine_command,
        description="Toggle automatic prompt refinement for current session",
        usage="auto-refine [on|off|toggle|status]",
    )

    router.register(
        name="setup-font",
        handler=setup_font_command,
        description="Setup terminal font configuration for VS Code",
        usage="setup-font [font-name] [--check|--list]",
    )
