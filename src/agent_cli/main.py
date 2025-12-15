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
def version() -> None:
    """Show the version and exit."""
    console.print(f"[bold cyan]ArchiFlow[/bold cyan] version [green]{__version__}[/green]")


if __name__ == "__main__":
    cli()
