"""
Session management commands.
"""

from typing import get_args
from rich.console import Console

from agent_cli.agents.factory import AgentFactoryError, AgentType, create_agent
from agent_cli.commands.router import CommandRouter
from agent_cli.session.manager import SessionManager
from agent_framework.agents.profiles import AGENT_PROFILES, list_profiles

console = Console()

# Get valid agent types from the AgentType literal
VALID_AGENT_TYPES = get_args(AgentType)  # ("coding", "simple", "analyzer", "reviewer", "product", "architect")


async def new_command(*args: str, **context: object) -> None:
    """
    Create a new agent session.

    Usage:
        /new [agent-type] [options...]

    Agent types:
        - coding: CodingAgent for software development tasks
        - simple: SimpleAgent for general conversations
        - simplev2: Enhanced SimpleAgent with profiles
        - analyzer: CodebaseAnalyzerAgent for codebase analysis and reporting
        - reviewer: CodeReviewAgent for code review tasks
        - product: ProductManagerAgent for product brainstorming
        - architect: TechLeadAgent for system architecture

    SimpleAgent v2 options:
        --profile <name>: Set agent profile (general, analyst, researcher, planner, assistant, developer)
        --prompt <text>: Custom system prompt
        --project-dir <path>: Project directory (optional)

    Examples:
        /new simplev2 --profile analyst
        /new simplev2 --profile custom --prompt "You are a creative writer"
        /new simplev2 --profile general --project-dir /path/to/project

    Args:
        *args: Command arguments
        **context: Context (expects 'session_manager' and 'repl_engine')
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

    # Parse agent type and options
    if not args:
        # Default to coding agent
        agent_type: AgentType = "coding"
        kwargs = {}
    else:
        agent_type_str = args[0].lower()
        if agent_type_str not in VALID_AGENT_TYPES:
            console.print(
                f"[red]Error: Unknown agent type '{agent_type_str}'[/red]\n"
                f"Supported types: {', '.join(VALID_AGENT_TYPES)}"
            )
            return
        agent_type = agent_type_str  # type: ignore[assignment]

        # Parse additional arguments
        kwargs = {}
        i = 1
        while i < len(args):
            arg = args[i]

            if agent_type == "simplev2":
                if arg == "--profile" and i + 1 < len(args):
                    kwargs["profile"] = args[i + 1]
                    i += 2
                elif arg == "--prompt" and i + 1 < len(args):
                    kwargs["custom_prompt"] = args[i + 1]
                    i += 2
                elif arg == "--project-dir" and i + 1 < len(args):
                    kwargs["project_directory"] = args[i + 1]
                    i += 2
                else:
                    # For simplev2, unknown options are treated as errors
                    console.print(f"[red]Error: Unknown option '{arg}' for simplev2 agent[/red]")
                    return
            else:
                # For other agents, treat extra args as project directory
                if i == 1:
                    kwargs["project_directory"] = arg
                i += 1

    # Create agent
    try:
        console.print(f"[cyan]Creating {agent_type} agent...[/cyan]")

        # Display configuration details
        if agent_type == "simplev2":
            profile = kwargs.get("profile", "general")
            console.print(f"[dim]Profile:[/dim] {profile}")
            if "custom_prompt" in kwargs:
                console.print(f"[dim]Custom prompt:[/dim] {kwargs['custom_prompt'][:50]}...")
        if "project_directory" in kwargs:
            console.print(f"[dim]Project directory:[/dim] {kwargs['project_directory']}")

        agent = create_agent(agent_type=agent_type, **kwargs)

        # Create session
        session = session_manager.create_session(agent=agent)

        # Subscribe to output to receive agent messages
        # This ensures messages are rendered immediately
        if not repl_engine.subscribed:
            repl_engine.subscribe_to_output()

        # Display success message
        console.print(
            f"[green]✓[/green] Created new {agent_type} agent session\n"
            f"[dim]Session ID:[/dim] {session.session_id}\n"
            f"[dim]Status:[/dim] Active"
        )

        console.print(
            "\n[cyan]You can now start chatting with the agent![/cyan]\n"
            "Type your message and press Enter."
        )

    except AgentFactoryError as e:
        console.print(f"[red]Error creating agent:[/red] {e}")
        console.print(
            "\n[yellow]Hint:[/yellow] Make sure you have set the OPENAI_API_KEY "
            "environment variable."
        )
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {e}")


async def sessions_command(**context: object) -> None:
    """
    List all sessions.

    Args:
        **context: Context (expects 'session_manager')
    """
    # Get session manager from context
    session_manager = context.get("session_manager")
    if not isinstance(session_manager, SessionManager):
        console.print("[red]Error: Session manager not available[/red]")
        return

    sessions = session_manager.list_sessions()

    if not sessions:
        console.print("[yellow]No active sessions[/yellow]")
        console.print("Use [bold]/new[/bold] to create a session")
        return

    # Display sessions
    console.print(f"[bold cyan]Active Sessions ({len(sessions)})[/bold cyan]\n")

    for session in sessions:
        active_marker = "●" if session.session_id == session_manager.active_session_id else "○"
        status = "Active" if session.active else "Closed"
        agent_type = session.agent.__class__.__name__

        console.print(
            f"{active_marker} [bold]{session.session_id}[/bold]\n"
            f"  Agent: {agent_type}\n"
            f"  Status: {status}\n"
        )


async def switch_command(*args: str, **context: object) -> None:
    """
    Switch to a different session.

    Usage:
        /switch <session-id>

    Args:
        *args: Command arguments (session ID)
        **context: Context (expects 'session_manager' and 'repl_engine')
    """
    # Get session manager from context
    session_manager = context.get("session_manager")
    if not isinstance(session_manager, SessionManager):
        console.print("[red]Error: Session manager not available[/red]")
        return

    # Get REPL engine from context (needed for re-subscribing to new session)
    repl_engine = context.get("repl_engine")
    if repl_engine is None:
        console.print("[red]Error: REPL engine not available[/red]")
        return

    if not args:
        console.print("[red]Error: Session ID required[/red]")
        console.print("Usage: /switch <session-id>")
        return

    session_id = args[0]
    session = session_manager.get_session(session_id)

    if not session:
        console.print(f"[red]Error: Session '{session_id}' not found[/red]")
        return

    session_manager.active_session_id = session_id

    # Re-subscribe to the new session's output
    # Mark as not subscribed so subscribe_to_output will set up new subscription
    repl_engine.subscribed = False
    repl_engine.subscribe_to_output()

    console.print(f"[green]✓[/green] Switched to session: {session_id}")


async def brainstorm_command(*args: str, **context: object) -> None:
    """
    Create a ProductManagerAgent session and start brainstorming.

    This is a convenience command that creates a product manager agent session
    automatically. The agent will help you brainstorm product ideas, refine
    requirements, and create comprehensive documentation.

    Usage:
        /brainstorm [project-directory]

    Args:
        *args: Command arguments (optional project directory)
        **context: Context (expects 'session_manager' and 'repl_engine')

    Examples:
        /brainstorm                    # Brainstorm for current directory
        /brainstorm /path/to/project   # Brainstorm for specific project
        /brainstorm ../myapp           # Brainstorm for relative path
    """
    # Get session manager from context
    session_manager = context.get("session_manager")
    if not isinstance(session_manager, SessionManager):
        console.print("[red]Error: Session manager not available[/red]")
        return

    # Get REPL engine from context (needed for agent_idle event)
    repl_engine = context.get("repl_engine")
    if repl_engine is None:
        console.print("[red]Error: REPL engine not available[/red]")
        return

    # Parse project directory (optional)
    project_directory = args[0] if args else None

    # Create product manager agent
    try:
        console.print("[bold cyan]💡 Starting Product Brainstorming Session[/bold cyan]\n")

        if project_directory:
            console.print(f"[dim]Project directory:[/dim] {project_directory}")
        else:
            console.print("[dim]Project directory:[/dim] Current directory")

        console.print("[dim]Agent type:[/dim] ProductManagerAgent")
        console.print()

        # Create agent using factory
        agent = create_agent(agent_type="product", project_directory=project_directory)

        # Create session
        session = session_manager.create_session(agent=agent)

        # Subscribe to output (similar to main REPL loop)
        if not repl_engine.subscribed:
            repl_engine.subscribe_to_output()

        # Display welcome message
        console.print(
            f"[green]✓[/green] Product Manager agent session created\n"
            f"[dim]Session ID:[/dim] {session.session_id}\n"
        )

        console.print(
            "\n[bold cyan]🎯 What to expect:[/bold cyan]\n"
            "The agent will help you:\n"
            "  1. [dim]Discover[/dim] - Understand your product vision and goals\n"
            "  2. [dim]Explore[/dim] - Dig into features, workflows, and edge cases\n"
            "  3. [dim]Prioritize[/dim] - Define MVP vs Phase 2 vs Future features\n"
            "  4. [dim]Document[/dim] - Create PRD, Technical Spec, and User Stories\n"
            "  5. [dim]Iterate[/dim] - Refine and expand based on your feedback\n"
        )

        console.print(
            "\n[bold green]📝 Deliverables:[/bold green]\n"
            "  • [yellow]PRODUCT_REQUIREMENTS.md[/yellow] - Complete PRD\n"
            "  • [yellow]TECHNICAL_SPEC.md[/yellow] - Technical specification\n"
            "  • [yellow]USER_STORIES.md[/yellow] - User stories with acceptance criteria\n"
        )

        console.print(
            "\n[cyan]The agent will start by asking about your product idea![/cyan]\n"
            "Be ready to discuss:\n"
            "  • What problem you're solving\n"
            "  • Who your target users are\n"
            "  • What makes your solution unique\n"
        )

        # Auto-start the brainstorming with a prompt
        console.print("[dim]→ Starting brainstorming session...[/dim]\n")

        # Send initial message to start the brainstorming
        initial_prompt = (
            "Hello! I'm ready to help you brainstorm your product idea. "
            "Let's start by understanding what you want to build. "
            "Tell me about your product idea - what problem are you trying to solve?"
        )
        success = session_manager.send_message(initial_prompt)

        # Clear agent_idle event to show spinner (same as in _process_input)
        if success:
            repl_engine.agent_idle.clear()

    except AgentFactoryError as e:
        console.print(f"[red]Error creating product manager agent:[/red] {e}")
        console.print(
            "\n[yellow]Hint:[/yellow] Make sure you have set the OPENAI_API_KEY "
            "environment variable."
        )
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {e}")


async def architect_command(*args: str, **context: object) -> None:
    """
    Create a TechLeadAgent session and start architecture design.

    This is a convenience command that creates a tech lead agent session
    automatically. The agent will help you design system architecture,
    make technical decisions, and create implementation plans.

    Usage:
        /architect [project-directory]

    Args:
        *args: Command arguments (optional project directory)
        **context: Context (expects 'session_manager' and 'repl_engine')

    Examples:
        /architect                    # Design architecture for current project
        /architect /path/to/project   # Design for specific project
        /architect ../myapp           # Design for relative path

    The architect agent will:
    - Detect existing documentation and adapt accordingly
    - Design system architecture and create RFCs
    - Break down the project into implementation phases
    - Create detailed task breakdowns for the coding agent
    - Provide technical guidance and best practices
    """
    # Get session manager from context
    session_manager = context.get("session_manager")
    if not isinstance(session_manager, SessionManager):
        console.print("[red]Error:[/red] Session manager not available")
        return

    # Get REPL engine from context
    repl_engine = context.get("repl_engine")
    if not repl_engine:
        console.print("[red]Error:[/red] REPL engine not available")
        return

    # Parse project directory (optional)
    project_directory = args[0] if args else None

    # Create tech lead agent
    try:
        console.print("[bold blue]🏗️  Starting Architecture Design Session[/bold blue]\n")

        if project_directory:
            console.print(f"[dim]Project directory:[/dim] {project_directory}")
        else:
            console.print("[dim]Project directory:[/dim] Current directory")

        console.print("[dim]Agent type:[/dim] TechLeadAgent")
        console.print()

        # Create agent using factory
        from agent_cli.agents.factory import create_agent
        agent = create_agent(agent_type="architect", project_directory=project_directory)

        # Create session
        session = session_manager.create_session(agent=agent)

        # Subscribe to output (similar to main REPL loop)
        if not repl_engine.subscribed:
            repl_engine.subscribe_to_output()

        # Display welcome message
        console.print(
            "\n[bold blue]🎯 Your Technical Lead is ready![/bold blue]\n"
            "I'll help you design a robust, scalable architecture for your project.\n"
        )

        console.print(
            "\n[bold cyan]🔍 What I'll do:[/bold cyan]\n"
            "The agent will automatically detect what you have and:\n"
            "  1. [dim]Analyze[/dim] - Review existing requirements and documentation\n"
            "  2. [dim]Discover[/dim] - Gather missing requirements (if needed)\n"
            "  3. [dim]Design[/dim] - Create system architecture and diagrams\n"
            "  4. [dim]Document[/dim] - Write RFCs and technical specifications\n"
            "  5. [dim]Plan[/dim] - Break down into implementation phases\n"
        )

        console.print(
            "\n[bold green]📋 Deliverables:[/bold green]\n"
            "  • [yellow]System Architecture Documentation[/yellow]\n"
            "  • [yellow]RFCs (Request for Comments)[/yellow]\n"
            "  • [yellow]Architecture Decision Records (ADRs)[/yellow]\n"
            "  • [yellow]Implementation Phases and Tasks[/yellow]\n"
            "  • [yellow]Technology Recommendations[/yellow]\n"
        )

        console.print(
            "\n[cyan]I'll start by examining your project and adapting to your needs...[/cyan]\n"
            "I'll automatically detect:\n"
            "  • Existing documentation (PRDs, specs)\n"
            "  • Current codebase (if any)\n"
            "  • Technology stack in use\n"
            "  • Project structure\n"
        )

        # Auto-start with a prompt based on detection
        console.print("[dim]→ Starting architecture assessment...[/dim]\n")

        # Send initial message to start the process
        initial_prompt = (
            "Hello! I'm your Tech Lead. I'm ready to help design the architecture for your project. "
            "Let me first assess what we're working with and then I'll guide you through the process."
        )
        success = session_manager.send_message(initial_prompt)

        # Clear agent_idle event to show spinner (same as in _process_input)
        if success:
            repl_engine.agent_idle.clear()

    except AgentFactoryError as e:
        console.print(f"[red]Error creating tech lead agent:[/red] {e}")
        console.print(
            "\n[yellow]Hint:[/yellow] Make sure you have set the OPENAI_API_KEY "
            "environment variable."
        )
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {e}")


async def profiles_command(*args: str, **context: object) -> None:
    """
    List available SimpleAgent v2 profiles.

    Usage:
        /profiles

    Displays all available profiles with their descriptions and capabilities.
    """
    console.print("\n[bold cyan]SimpleAgent v2 Profiles[/bold cyan]\n")

    for profile_name in list_profiles():
        profile = AGENT_PROFILES[profile_name]
        console.print(f"[bold]{profile_name}[/bold]")
        console.print(f"  [dim]Description:[/dim] {profile.description}")

        if profile.capabilities:
            console.print(f"  [dim]Capabilities:[/dim] {', '.join(profile.capabilities)}")

        if profile.tool_categories:
            console.print(f"  [dim]Tool Categories:[/dim] {', '.join(profile.tool_categories)}")

        console.print()  # Empty line for readability

    console.print("[yellow]Usage Examples:[/yellow]")
    console.print("  /new simplev2 --profile general")
    console.print("  /new simplev2 --profile analyst --project-dir ./my-project")
    console.print("  /new simplev2 --profile custom --prompt \"You are a creative writing assistant\"")


async def code_command(*args: str, **context: object) -> None:
    """
    Create a CodingAgent session for software development tasks.

    This is a convenience command that creates a coding agent session
    automatically. The coding agent can write code, fix bugs, add features,
    and help with development tasks.

    Usage:
        /code [project-directory]

    Args:
        *args: Command arguments (optional project directory)
        **context: Context (expects 'session_manager' and 'repl_engine')

    Examples:
        /code                         # Start coding agent for current directory
        /code /path/to/project        # Start coding agent for specific project
        /code ../myapp               # Start coding agent for relative path

    The coding agent will:
    - Read, write, and edit code files
    - Run bash commands and scripts
    - Search and analyze codebase
    - Fix bugs and implement features
    - Help with testing and debugging
    - Manage TODO lists for task tracking
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

    # Parse project directory (optional)
    project_directory = args[0] if args else None

    # Create coding agent
    try:
        console.print("[bold green]💻 Starting Coding Agent Session[/bold green]\n")

        if project_directory:
            console.print(f"[dim]Project directory:[/dim] {project_directory}")
        else:
            console.print("[dim]Project directory:[/dim] Current directory")

        console.print("[dim]Agent type:[/dim] CodingAgent")
        console.print()

        # Create agent using factory
        agent = create_agent(agent_type="coding", project_directory=project_directory)

        # Create session
        session = session_manager.create_session(agent=agent)

        # Subscribe to output (similar to main REPL loop)
        if not repl_engine.subscribed:
            repl_engine.subscribe_to_output()

        # Display success message
        console.print(
            f"[green]✓[/green] Coding agent session created\n"
            f"[dim]Session ID:[/dim] {session.session_id}\n"
        )

        console.print(
            "\n[bold green]🚀 What I can help you with:[/bold green]\n"
            "The coding agent can assist with:\n"
            "  • [dim]Write code[/dim] - Create new files and implement features\n"
            "  • [dim]Fix bugs[/dim] - Debug and repair issues\n"
            "  •[dim] Refactor[/dim] - Improve code structure and quality\n"
            "  • [dim]Run commands[/dim] - Execute bash commands and scripts\n"
            "  • [dim]Search code[/dim] - Find patterns and analyze codebase\n"
            "  • [dim]Write tests[/dim] - Create and run unit tests\n"
            "  • [dim]Task tracking[/dim] - Manage TODO lists and progress\n"
        )

        console.print(
            "\n[cyan]Ready to code! Tell me what you'd like to work on.[/cyan]\n"
            "Examples:\n"
            "  • 'Fix the login bug'\n"
            "  • 'Add a new API endpoint'\n"
            "  • 'Refactor the user service'\n"
            "  • 'Write tests for the payment module'"
        )

    except AgentFactoryError as e:
        console.print(f"[red]Error creating coding agent:[/red] {e}")
        console.print(
            "\n[yellow]Hint:[/yellow] Make sure you have set the OPENAI_API_KEY "
            "environment variable."
        )
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {e}")


async def analyzer_command(*args: str, **context: object) -> None:
    """
    Create a CodebaseAnalyzerAgent session and start analysis.

    This is a convenience command that creates an analyzer agent session
    automatically. It's equivalent to /new analyzer [project-dir] but with
    better messaging for the analysis workflow.

    Usage:
        /analyzer [project-directory]

    Args:
        *args: Command arguments (optional project directory)
        **context: Context (expects 'session_manager' and 'repl_engine')

    Examples:
        /analyzer                    # Analyze current directory
        /analyzer /path/to/project   # Analyze specific project
        /analyzer ../myapp           # Analyze relative path
    """
    # Get session manager from context
    session_manager = context.get("session_manager")
    if not isinstance(session_manager, SessionManager):
        console.print("[red]Error: Session manager not available[/red]")
        return

    # Get REPL engine from context (needed for agent_idle event)
    repl_engine = context.get("repl_engine")
    if repl_engine is None:
        console.print("[red]Error: REPL engine not available[/red]")
        return

    # Parse project directory (optional)
    project_directory = args[0] if args else None

    # Create analyzer agent
    try:
        console.print("[bold cyan]🔍 Starting Codebase Analysis[/bold cyan]\n")

        if project_directory:
            console.print(f"[dim]Project directory:[/dim] {project_directory}")
        else:
            console.print("[dim]Project directory:[/dim] Current directory")

        console.print("[dim]Agent type:[/dim] CodebaseAnalyzerAgent")
        console.print()

        # Create agent using factory
        agent = create_agent(agent_type="analyzer", project_directory=project_directory)

        # Create session
        session = session_manager.create_session(agent=agent)

        # Subscribe to output (similar to main REPL loop)
        if not repl_engine.subscribed:
            repl_engine.subscribe_to_output()

        # Display welcome message
        console.print(
            f"[green]✓[/green] Analyzer agent session created\n"
            f"[dim]Session ID:[/dim] {session.session_id}\n"
        )

        console.print(
            "\n[bold cyan]📊 What to expect:[/bold cyan]\n"
            "The analyzer will systematically:\n"
            "  1. [dim]Discover[/dim] - Scan project structure and files\n"
            "  2. [dim]Catalog[/dim] - Categorize files and identify components\n"
            "  3. [dim]Analyze[/dim] - Examine code quality and architecture\n"
            "  4. [dim]Measure[/dim] - Calculate metrics and statistics\n"
            "  5. [dim]Report[/dim] - Generate comprehensive analysis\n"
        )

        console.print(
            "\n[bold green]📝 Output:[/bold green]\n"
            "  • Console summary with key findings\n"
            "  • Detailed report saved to: [yellow]CODEBASE_ANALYSIS_REPORT.md[/yellow]\n"
        )

        console.print(
            "\n[cyan]The agent will start working automatically![/cyan]\n"
            "You can ask questions or provide guidance at any time.\n"
        )

        # Auto-start the analysis with a prompt
        console.print("[dim]→ Initiating analysis...[/dim]\n")

        # Send initial message to start the analysis
        initial_prompt = (
            "Please analyze this codebase systematically. Follow your standard "
            "5-phase workflow (Discover, Catalog, Analyze, Measure, Report) and "
            "generate a comprehensive analysis report."
        )
        success = session_manager.send_message(initial_prompt)

        # Clear agent_idle event to show spinner (same as in _process_input)
        if success:
            repl_engine.agent_idle.clear()

    except AgentFactoryError as e:
        console.print(f"[red]Error creating analyzer agent:[/red] {e}")
        console.print(
            "\n[yellow]Hint:[/yellow] Make sure you have set the OPENAI_API_KEY "
            "environment variable."
        )
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {e}")


def register_session_commands(router: CommandRouter) -> None:
    """
    Register session management commands.

    Args:
        router: Command router to register with
    """
    router.register(
        name="new",
        handler=new_command,
        description="Create a new agent session",
        usage=f"new [agent-type] [options...]  # agent-type: {', '.join(VALID_AGENT_TYPES)}",
    )

    router.register(
        name="profiles",
        handler=profiles_command,
        description="List available SimpleAgent v2 profiles",
    )

    router.register(
        name="sessions",
        handler=sessions_command,
        description="List all active sessions",
    )

    router.register(
        name="switch",
        handler=switch_command,
        description="Switch to a different session",
        usage="switch <session-id>",
    )

    router.register(
        name="code",
        handler=code_command,
        description="Start coding agent for software development tasks",
        usage="code [project-directory]",
    )

    router.register(
        name="analyzer",
        handler=analyzer_command,
        description="Start codebase analysis (creates analyzer agent and begins analysis)",
        usage="analyzer [project-directory]",
    )

    router.register(
        name="brainstorm",
        handler=brainstorm_command,
        description="Start product brainstorming (creates product manager agent for requirements gathering)",
        usage="brainstorm [project-directory]",
    )

    router.register(
        name="architect",
        handler=architect_command,
        description="Start architecture design (creates tech lead agent for system design and planning)",
        usage="architect [project-directory]",
    )
