"""
Main CLI entry point for ArchiFlow.
"""

import asyncio
import sys
from pathlib import Path

import click
from rich.console import Console

from agent_cli import __version__

console = Console()


@click.group(invoke_without_command=True)
@click.option("--version", is_flag=True, help="Show version and exit")
@click.option(
    "--config",
    type=click.Path(exists=True, path_type=Path),
    help="Path to configuration file",
)
@click.option("--debug", "-d", is_flag=True, help="Enable debug logging")
@click.option("--info", "-i", is_flag=True, help="Enable info logging")
@click.pass_context
def cli(ctx: click.Context, version: bool, config: Path | None, debug: bool, info: bool) -> None:
    """
    ArchiFlow - Interactive AI agent framework for architecture and development.

    Run without arguments to start the interactive REPL.
    Use subcommands for specific operations.
    """
    # Ensure context object exists
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config
    ctx.obj["debug"] = debug

    # Configure logging if debug is enabled
    if debug or info:
        import logging
        import os
        from datetime import datetime

        level = logging.DEBUG if debug else logging.INFO

        # Create logs directory if it doesn't exist
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)

        # Create log file with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = logs_dir / f"archiflow_{timestamp}.log"

        # Configure file handler for all logs
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(file_formatter)

        # Configure console handler
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(level)
        console_formatter = logging.Formatter(
            "%(name)s - %(levelname)s - %(message)s"
        )
        console_handler.setFormatter(console_formatter)

        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(level)
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)

        # Special handler for tool results - save to dedicated file
        tool_result_log_file = logs_dir / f"tool_results_{timestamp}.log"
        tool_result_handler = logging.FileHandler(tool_result_log_file)
        tool_result_handler.setLevel(logging.DEBUG)  # Capture all tool result logs

        # Create a custom logger for tool results
        tool_result_logger = logging.getLogger("tool_results")
        tool_result_logger.setLevel(logging.DEBUG)
        tool_result_logger.addHandler(tool_result_handler)
        tool_result_logger.addHandler(console_handler)

        # Prevent propagation to avoid duplicate logs
        tool_result_logger.propagate = False

        # Log initialization
        logging.info(f"Logging initialized. Log file: {log_file}")
        logging.info(f"Tool results log file: {tool_result_log_file}")

    if version:
        console.print(f"[bold cyan]ArchiFlow[/bold cyan] version [green]{__version__}[/green]")
        return

    if ctx.invoked_subcommand is None:
        # No subcommand provided, start REPL
        try:
            # Import here to avoid circular imports and allow CLI to load quickly
            from agent_cli.repl.engine import REPLEngine

            repl = REPLEngine(config_path=config)
            asyncio.run(repl.run())
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted by user[/yellow]")
            sys.exit(0)
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {e}")
            if "--debug" in sys.argv or "-d" in sys.argv:
                raise
            sys.exit(1)


@cli.command()
@click.pass_context
def repl(ctx: click.Context) -> None:
    """Start the interactive REPL."""
    try:
        from agent_cli.repl.engine import REPLEngine

        config_path = ctx.obj.get("config_path")
        repl_engine = REPLEngine(config_path=config_path)
        asyncio.run(repl_engine.run())
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        if "--debug" in sys.argv or "-d" in sys.argv:
            raise
        sys.exit(1)


@cli.command()
@click.option("--project-dir", "-p", type=click.Path(exists=True, path_type=Path), help="Project directory for research output")
def research(project_dir: Path | None) -> None:
    """Start a ResearchAgent session for comprehensive research."""
    try:
        # Import here to avoid circular imports
        from agent_cli.agents.factory import create_research_agent
        from agent_framework.llm.glm_provider import GLMProvider
        from agent_framework.config.env_loader import load_env

        # Load environment variables
        load_env()

        # Create LLM provider
        import os
        api_key = os.getenv("ZAI_API_KEY")
        if not api_key:
            console.print("[bold red]Error:[/bold red] ZAI_API_KEY not found in environment")
            sys.exit(1)

        llm = GLMProvider(api_key=api_key)

        # Create research agent
        agent = create_research_agent(
            project_directory=str(project_dir) if project_dir else None
        )

        # Create a simple session for the research agent
        from agent_framework.messages.types import UserMessage
        from agent_framework.agents.research_agent import ResearchAgent

        # Start interactive research session
        console.print("[bold cyan]Research Agent[/bold cyan] [green]Ready![/green]")
        console.print("\n[bold]Research Agent Capabilities:[/bold]")
        console.print("• Comprehensive research on any topic")
        console.print("• Multi-source information gathering")
        console.print("• Systematic analysis and synthesis")
        console.print("• Professional report generation")
        console.print("\n[yellow]Example:[/yellow] 'Research the impact of AI on job markets in 2024'")
        console.print("\n[bold]Type your research topic or '/help' for commands.[/bold]\n")

        # Simple interactive loop
        while True:
            try:
                user_input = input("research> ").strip()

                if not user_input:
                    continue

                if user_input.lower() in ['/exit', '/quit']:
                    console.print("[yellow]Exiting research session...[/yellow]")
                    break

                if user_input.lower() == '/help':
                    console.print("\n[bold]Research Commands:[/bold]")
                    console.print("• [Your topic] - Start research on a topic")
                    console.print("• /exit or /quit - Exit the research session")
                    console.print("• /list - List research files in session")
                    console.print("\n[bold]Research Workflow:[/bold]")
                    console.print("1. Planning - Define research scope and questions")
                    console.print("2. Gathering - Collect information from sources")
                    console.print("3. Analysis - Synthesize and organize findings")
                    console.print("4. Writing - Generate comprehensive report")
                    console.print("5. Review - Iterative refinement with your feedback")
                    continue

                if user_input.lower() == '/list':
                    import glob
                    session_dir = agent.project_directory
                    if os.path.exists(session_dir):
                        files = glob.glob(os.path.join(session_dir, "*"))
                        if files:
                            console.print(f"\n[bold]Research files in {session_dir}:[/bold]")
                            for f in files:
                                console.print(f"  • {os.path.basename(f)}")
                        else:
                            console.print("[yellow]No research files yet[/yellow]")
                    continue

                # Process user input
                message = UserMessage(
                    session_id=agent.session_id,
                    sequence=0,
                    content=user_input
                )

                response = agent.step(message)

                if response:
                    if hasattr(response, 'tool_calls') and response.tool_calls:
                        # Execute tools and show results
                        for tool_call in response.tool_calls:
                            console.print(f"\n[dim]Executing: {tool_call.tool_name}[/dim]")
                            # Tool execution would be handled by the runtime in a real scenario
                            console.print("[dim]Tools are being executed...[/dim]")
                    elif hasattr(response, 'content'):
                        console.print(f"\n{response.content}")
                    else:
                        console.print(f"\n[Response received: {type(response).__name__}]")

            except KeyboardInterrupt:
                console.print("\n[yellow]Interrupted by user[/yellow]")
                break
            except Exception as e:
                console.print(f"\n[bold red]Error:[/bold red] {e}")
                if "--debug" in sys.argv or "-d" in sys.argv:
                    raise

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        if "--debug" in sys.argv or "-d" in sys.argv:
            raise
        sys.exit(1)


@cli.command()
@click.option("--project-dir", "-p", type=click.Path(exists=True, path_type=Path), help="Project directory for code development")
@click.option("--mode", "-m", type=click.Choice(['ideation', 'implementation', 'debug', 'refactor', 'feature', 'review', 'test']),
              help="Force a specific mode")
def coding(project_dir: Path | None, mode: str | None) -> None:
    """Start a CodingAgentV3 session for advanced development."""
    try:
        # Import here to avoid circular imports
        from agent_cli.agents.factory import create_coding_agent_v3
        from agent_framework.llm.glm_provider import GLMProvider
        from agent_framework.config.env_loader import load_env

        # Load environment variables
        load_env()

        # Create LLM provider
        import os
        api_key = os.getenv("ZAI_API_KEY")
        if not api_key:
            console.print("[bold red]Error:[/bold red] ZAI_API_KEY not found in environment")
            sys.exit(1)

        llm = GLMProvider(api_key=api_key)

        # Create coding agent v3
        agent = create_coding_agent_v3(
            project_directory=str(project_dir) if project_dir else None
        )

        # Create a simple session for the coding agent
        from agent_framework.messages.types import UserMessage

        # Start interactive coding session
        console.print("[bold cyan]Coding Agent V3[/bold cyan] [green]Ready![/green]")
        console.print("\n[bold]Coding Agent V3 Capabilities:[/bold]")
        console.print("• [Ideation] Transform ideas into specifications")
        console.print("• [Implementation] Write code from specifications")
        console.print("• [Debug] Fix errors systematically")
        console.print("• [Refactor] Improve code quality")
        console.print("• [Feature] Add new functionality")
        console.print("• [Review] Comprehensive code analysis")
        console.print("• [Test] Create comprehensive test suites")

        if mode:
            console.print(f"\n[yellow]Note: Forced mode: {mode}[/yellow]")
            console.print("[yellow]The agent will still detect the best mode based on context[/yellow]")

        console.print("\n[yellow]Examples:[/yellow]")
        console.print("• 'Create a REST API for user management'")
        console.print("• 'Debug this TypeError: NoneType object is not callable'")
        console.print("• 'Refactor this function for better readability'")
        console.print("\n[bold]Type your coding task or '/help' for commands.[/bold]\n")

        # Simple interactive loop
        while True:
            try:
                user_input = input("coding> ").strip()

                if not user_input:
                    continue

                if user_input.lower() in ['/exit', '/quit']:
                    console.print("[yellow]Exiting coding session...[/yellow]")
                    break

                if user_input.lower() == '/help':
                    console.print("\n[bold]Coding Commands:[/bold]")
                    console.print("• [Your task] - Start coding task")
                    console.print("• /exit or /quit - Exit the coding session")
                    console.print("• /list - List files in session")
                    console.print("• /mode - Show current mode information")
                    console.print("\n[bold]Available Modes:[/bold]")
                    console.print("• Ideation - Create specifications from ideas")
                    console.print("• Implementation - Write code from specs")
                    console.print("• Debug - Fix errors and issues")
                    console.print("• Refactor - Improve code quality")
                    console.print("• Feature - Add new functionality")
                    console.print("• Review - Analyze code quality")
                    console.print("• Test - Create test suites")
                    continue

                if user_input.lower() == '/list':
                    import glob
                    session_dir = agent.project_directory
                    if os.path.exists(session_dir):
                        files = glob.glob(os.path.join(session_dir, "**/*"), recursive=True)
                        files = [f for f in files if os.path.isfile(f)]
                        if files:
                            console.print(f"\n[bold]Files in {session_dir}:[/bold]")
                            for f in sorted(files):
                                rel_path = os.path.relpath(f, session_dir)
                                if rel_path.startswith('src/'):
                                    console.print(f"  📄 {rel_path}")
                                elif rel_path.startswith('tests/'):
                                    console.print(f"  🧪 {rel_path}")
                                elif rel_path.startswith('docs/'):
                                    console.print(f"  📚 {rel_path}")
                                else:
                                    console.print(f"  📋 {rel_path}")
                        else:
                            console.print("[yellow]No files created yet[/yellow]")
                    continue

                if user_input.lower() == '/mode':
                    console.print("\n[bold]Current Session Context:[/bold]")
                    console.print(f"  Session ID: {agent.session_id}")
                    console.print(f"  Directory: {agent.project_directory}")

                    # Check current artifacts
                    import json
                    artifacts = []
                    session_path = Path(agent.project_directory)

                    if (session_path / "specs.json").exists():
                        artifacts.append("✅ Specifications")
                    if len(list(session_path.glob("src/*.*"))) > 0:
                        artifacts.append("✅ Source Code")
                    if len(list(session_path.glob("tests/*.*"))) > 0:
                        artifacts.append("✅ Tests")
                    if (session_path / "debug_report.json").exists():
                        artifacts.append("✅ Debug Report")
                    if (session_path / "refactor_plan.json").exists():
                        artifacts.append("✅ Refactor Plan")
                    if (session_path / "code_review.json").exists():
                        artifacts.append("✅ Code Review")

                    if artifacts:
                        console.print("\n[bold]Artifacts:[/bold]")
                        for artifact in artifacts:
                            console.print(f"  {artifact}")
                    else:
                        console.print("\n[yellow]No artifacts yet[/yellow]")
                    continue

                # Process user input
                message = UserMessage(
                    session_id=agent.session_id,
                    sequence=0,
                    content=user_input
                )

                response = agent.step(message)

                if response:
                    if hasattr(response, 'tool_calls') and response.tool_calls:
                        # Execute tools and show results
                        console.print(f"\n[dim]Agent is working...[/dim]")
                        for tool_call in response.tool_calls:
                            console.print(f"  🔧 {tool_call.tool_name}")
                            # Tool execution would be handled by the runtime in a real scenario
                            console.print("[dim]Executing tools...[/dim]")
                    elif hasattr(response, 'content'):
                        # Show the agent's response
                        console.print(f"\n{response.content}")
                    else:
                        console.print(f"\n[Response received: {type(response).__name__}]")

            except KeyboardInterrupt:
                console.print("\n[yellow]Interrupted by user[/yellow]")
                break
            except Exception as e:
                console.print(f"\n[bold red]Error:[/bold red] {e}")
                if "--debug" in sys.argv or "-d" in sys.argv:
                    raise

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        if "--debug" in sys.argv or "-d" in sys.argv:
            raise
        sys.exit(1)


@cli.command()
def version() -> None:
    """Show the version and exit."""
    console.print(f"[bold cyan]ArchiFlow[/bold cyan] version [green]{__version__}[/green]")


if __name__ == "__main__":
    cli()
