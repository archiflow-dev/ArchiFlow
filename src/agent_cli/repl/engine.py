"""
REPL Engine - Interactive prompt for ArchiFlow.
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from prompt_toolkit.key_binding import KeyBindings
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from agent_cli import __version__
from agent_cli.commands.router import CommandRouter
from agent_cli.commands.session import register_session_commands
from agent_cli.commands.system import SystemCommandHandler
from agent_cli.commands.utility import register_utility_commands
from agent_cli.output.renderer import OutputRenderer
from agent_cli.repl.shell_context import ShellContext
from agent_cli.session.manager import SessionManager

console = Console()
logger = logging.getLogger(__name__)
# Special logger for tool results
tool_result_logger = logging.getLogger("tool_results")


class REPLEngine:
    """
    Interactive REPL engine for ArchiFlow.

    Provides an interactive prompt for users to communicate with AI agents.
    """

    def __init__(self, config_path: Path | None = None) -> None:
        """
        Initialize the REPL engine.

        Args:
            config_path: Optional path to configuration file
        """
        self.config_path = config_path
        self.running = False

        # Set up history file
        history_path = Path.home() / ".agent_cli_history"
        self.history = FileHistory(str(history_path))

        # Lazy initialization - session will be created when run() is called
        self.session: PromptSession[str] | None = None

        # Set up session manager
        self.session_manager = SessionManager()

        # Set up command router
        self.router = CommandRouter()
        register_utility_commands(self.router)
        register_session_commands(self.router)

        # Set up output renderer - use the same console instance
        # Get tool result line limit from environment variable or use default
        tool_result_line_limit = int(os.environ.get("ARCHIFLOW_TOOL_RESULT_LINES", "20"))
        self.renderer = OutputRenderer(console_instance=console, tool_result_line_limit=tool_result_line_limit)

        # Message queue for async communication
        self.message_queue: asyncio.Queue[Any] = asyncio.Queue()

        # Track which sessions we're subscribed to
        self.subscribed_sessions: set[str] = set()

        # Event to track if agent is idle (waiting for input) or running
        # Start as set (idle) so we can accept initial input
        self.agent_idle = asyncio.Event()
        self.agent_idle.set()

        # Event to track if agent should be aborted
        self.agent_abort = asyncio.Event()
        self.agent_abort.clear()

        # Prompt improvement - Phase 1: Vagueness detection (LLM-based)
        # Use lazy initialization to speed up startup
        self._vagueness_detector = None
        self.enable_vagueness_check = True  # Can be disabled via config

        # Prompt improvement - Phase 2: Auto-improvement (LLM-based)
        # Use lazy initialization to speed up startup
        self._prompt_improver = None
        self.enable_prompt_improvement = True

        # System command support - auto-detection with whitelist
        self.shell_context = ShellContext()
        self.system_handler = SystemCommandHandler(
            self.shell_context,
            self.session_manager  # Pass session manager for agent sync
        )

        
    @property
    def vagueness_detector(self):
        """Lazy initialization of vagueness detector."""
        if self._vagueness_detector is None:
            from agent_cli.prompt_improvement import LLMVaguenessDetector
            self._vagueness_detector = LLMVaguenessDetector(
                fallback_to_heuristic=True
            )
        return self._vagueness_detector

    @property
    def prompt_improver(self):
        """Lazy initialization of prompt improver."""
        if self._prompt_improver is None:
            try:
                from agent_cli.prompt_improvement import LLMPromptImprover
                self._prompt_improver = LLMPromptImprover()
            except Exception as e:
                logger.warning(f"Failed to initialize prompt improver: {e}")
                self._prompt_improver = None
        return self._prompt_improver

    def _create_style(self) -> Style:
        """Create the prompt style."""
        return Style.from_dict(
            {
                "prompt": "ansicyan bold",
                "path": "ansiblue",
            }
        )

    def _handle_abort(self) -> None:
        """Handle agent abort when Escape key is pressed."""
        if not self.agent_idle.is_set():
            # Agent is running, send abort signal
            console.print("\n[red]⚡ Aborting agent execution...[/red]")

            # Send abort message to active session
            success = self.session_manager.abort_agent()

            if success:
                # Set the abort event
                self.agent_abort.set()

                # Also set idle to return control to user
                self.agent_idle.set()

                console.print("[yellow]Agent execution aborted. Press Enter to continue.[/yellow]")
            else:
                console.print("[red]Failed to abort agent - no active session[/red]")
        else:
            # Agent is idle, ignore Escape key
            console.print("\n[dim]Agent is idle - nothing to abort[/dim]")

    
    def _get_key_bindings(self) -> KeyBindings:
        """Create key bindings for the prompt session."""
        kb = KeyBindings()

        @kb.add('escape')
        def _(event):
            """Handle Escape key press to abort agent execution."""
            # Only handle abort if agent is running
            if not self.agent_idle.is_set():
                # Clear any current input
                event.app.current_buffer.reset()
                # Handle the abort
                self._handle_abort()
                # Don't show the escape character
                event.app.current_buffer.insert_text("")
            else:
                # Agent is idle, ignore Escape
                pass

        return kb

    def _get_prompt(self) -> str:
        """
        Get the current prompt string with directory indicator.

        Returns:
            Formatted prompt string with current directory
        """
        cwd_display = self.shell_context.get_cwd_display()
        return [
            ("class:path", f"[{cwd_display}]"),
            ("", " "),
            ("class:prompt", ">>> "),
        ]

    def _display_welcome(self) -> None:
        """Display welcome message."""
        # Display ASCII art banner
        banner = r"""
    _             _     _ _____ _
   / \   _ __ ___| |__ (_)  ___| | _____      __
  / _ \ | '__/ __| '_ \| | |_  | |/ _ \ \ /\ / /
 / ___ \| | | (__| | | | |  _| | | (_) \ V  V /
/_/   \_\_|  \___|_| |_|_|_|   |_|\___/ \_/\_/
        """
        console.print(f"[bold orange1]{banner}[/bold orange1]")

        welcome_text = f"""
**Version:** {__version__}

Welcome to ArchiFlow - the interactive AI agent framework!

You can:
- Chat with AI agents by typing your message
- Use system commands directly (cd, ls, pwd, git, clear, etc.)
- Use `/shell-commands` to see all available shell commands
- Use `/help` to see available CLI commands
- Use `/exit` or press Ctrl+D to quit
- Press **Ctrl+C** to abort a running agent during thinking
- Press **Escape** to abort when prompted for input

The prompt shows your current directory: `[path] >>> `

Type your message and press Enter to begin.
        """
        console.print(Panel(Markdown(welcome_text.strip()), border_style="orange1"))
        console.print()

    def subscribe_to_output(self, session_id: str | None = None) -> None:
        """
        Subscribe to client_topic to receive messages from agent.

        This sets up a broker subscriber that puts messages into the async queue
        for processing by the message renderer.

        Args:
            session_id: Optional session ID to subscribe to. If None, uses active session.
        """
        # Get session to subscribe to
        if session_id:
            session = self.session_manager.get_session(session_id)
        else:
            session = self.session_manager.get_active_session()

        if not session:
            return

        # Check if already subscribed to this session
        if session.session_id in self.subscribed_sessions:
            logger.debug(
                "Already subscribed to session %s, skipping",
                session.session_id
            )
            return

        # Define callback that puts messages into the queue
        async def on_message(message: Any) -> None:
            """Callback for broker messages."""
            # Extract payload if it's a Message wrapper
            if hasattr(message, 'payload'):
                payload = message.payload
            else:
                payload = message

            # Log message reception
            msg_type = payload.get("type", "Unknown")
            tool_name = payload.get("tool_name", "")

            logger.debug(
                "Received message on client_topic %s: type=%s, tool=%s, session=%s",
                session.context.client_topic,
                msg_type,
                tool_name,
                session.session_id
            )

            # Special logging for ToolResult messages
            if msg_type == "ToolResult":
                logger.info(
                    "ToolResult received: tool=%s, status=%s, result_preview=%s..., session=%s",
                    tool_name,
                    payload.get("status"),
                    payload.get("result", "")[:50],
                    session.session_id
                )
                # Also log to dedicated tool result logger with more detail
                tool_result_logger.info(
                    "=== TOOL RESULT RECEIVED ===\n"
                    f"Tool: {tool_name}\n"
                    f"Status: {payload.get('status')}\n"
                    f"Result: {payload.get('result', '')}\n"
                    f"Metadata: {payload.get('metadata', {})}\n"
                    f"Session: {session.session_id}\n"
                    "============================="
                )

            # Put message in queue for async processing
            await self.message_queue.put(message)

        logger.info(
            "Subscribing to client_topic %s for session %s",
            session.context.client_topic,
            session.session_id
        )

        # Subscribe to client_topic
        session.broker.subscribe(session.context.client_topic, on_message)

        # Track this subscription
        self.subscribed_sessions.add(session.session_id)

        logger.info(
            "Successfully subscribed to client_topic %s for session %s",
            session.context.client_topic,
            session.session_id
        )

    async def process_messages(self) -> None:
        """
        Process messages from the queue and render them.

        This runs in a background task and continuously processes messages
        from the agent.
        """
        while self.running:
            try:
                # Wait for message with timeout
                message = await asyncio.wait_for(self.message_queue.get(), timeout=0.1)

                # Log before rendering
                if hasattr(message, "payload"):
                    payload = message.payload
                    msg_type = payload.get("type", "")
                else:
                    msg_type = message.get("type", "")

                logger.debug(
                    "Processing message from queue: type=%s",
                    msg_type
                )

                # Render the message
                await self.render_message(message)

            except asyncio.TimeoutError:
                # No message available, continue
                continue
            except Exception as e:
                self.renderer.error(f"Error processing message: {e}")

    async def render_message(self, message: Any) -> None:
        """
        Render a message from the agent.

        Args:
            message: The message object from the broker
        """
        # Extract payload if it's a Message wrapper
        if hasattr(message, "payload"):
            message = message.payload

        msg_type = message.get("type", "")
        logger.debug(f"Rendering message type: {msg_type}")

        try:
            # Special logging for ToolResult rendering
            if msg_type == "ToolResult":
                tool_name = message.get("tool_name", "")
                status = message.get("status", "")
                result = message.get("result", "")

                logger.info(
                    "Rendering ToolResult: tool=%s, status=%s",
                    tool_name,
                    status
                )
                logger.debug(
                    "ToolResult content: %s",
                    result[:200] + "..." if len(result) > 200 else result
                )
                # Also log to dedicated tool result logger
                tool_result_logger.info(
                    "=== RENDERING TOOL RESULT ===\n"
                    f"Tool: {tool_name}\n"
                    f"Status: {status}\n"
                    f"Result Length: {len(result)}\n"
                    f"Content Preview: {result[:500]}{'...' if len(result) > 500 else ''}\n"
                    "==============================="
                )

            self.renderer.render_event(message)

            # Log after successful rendering
            if msg_type == "ToolResult":
                logger.info("Successfully rendered ToolResult message")
                tool_result_logger.info(
                    "=== TOOL RESULT SUCCESSFULLY RENDERED ===\n"
                    f"Tool: {message.get('tool_name', '')}\n"
                    "========================================"
                )

        except Exception as e:
            logger.error(
                "Error rendering message type %s: %s",
                msg_type,
                str(e),
                exc_info=True
            )
            self.renderer.error(f"Error rendering message: {e}")
        finally:
            # Check if we should unblock input
            if msg_type in ("AGENT_FINISHED", "WAIT_FOR_USER_INPUT", "Error", "AbortAck"):
                logger.debug(f"Setting agent_idle event for message type: {msg_type}")
                self.agent_idle.set()

    async def run(self) -> None:
        """
        Run the REPL loop.

        This method starts the interactive prompt and processes user input.
        """
        self.running = True
        self._display_welcome()

        # Initialize prompt session here (lazy initialization for testability)
        if self.session is None:
            self.session = PromptSession(
                history=self.history,
                style=self._create_style(),
                key_bindings=self._get_key_bindings(),
            )

        # Start message processing task
        message_task = asyncio.create_task(self.process_messages())

        try:
            while self.running:
                try:
                    # Subscribe to output if we have an active session
                    active_session = self.session_manager.get_active_session()
                    if active_session and active_session.session_id not in self.subscribed_sessions:
                        self.subscribe_to_output()

                    # Get user input with dynamic prompt showing current directory
                    user_input = await self.session.prompt_async(
                        self._get_prompt(), multiline=False
                    )

                    # Skip empty input
                    if not user_input.strip():
                        continue

                    # Process input
                    await self._process_input(user_input)

                    # Wait for agent if it's running
                    # Note: We only wait if there's actually an agent running
                    # The agent_idle event is set when agent is idle and cleared when agent is working
                    if not self.agent_idle.is_set():
                        logger.debug("Starting spinner, waiting for agent to finish...")

                        # Check if abort was triggered from previous iteration
                        if self.agent_abort.is_set():
                            self.agent_abort.clear()
                            continue

                        with console.status(
                            "[bold green]Thinking...[/bold green]",
                            spinner="dots"
                        ) as status:
                            # Wait for agent to finish
                            # Note: prompt_toolkit key bindings don't work during async/await
                            # The user must use Ctrl+C to abort during thinking phase
                            # Escape key works only during prompt input phase
                            try:
                                await self.agent_idle.wait()
                            except asyncio.CancelledError:
                                # User pressed Ctrl+C
                                self._handle_abort()
                                self.agent_idle.set()

                            # Explicitly stop to ensure it updates
                            status.stop()

                        logger.debug("Spinner stopped, agent is idle")
                    else:
                        # Agent is idle, this is normal - we can accept new input
                        pass

                except KeyboardInterrupt:
                    # Ctrl+C - cancel current line
                    console.print("[yellow]Cancelled[/yellow]")
                    self.agent_idle.set()
                    continue

                except EOFError:
                    # Ctrl+D - exit
                    console.print("\n[cyan]Goodbye![/cyan]")
                    break

        finally:
            self.running = False
            # Clean up all subscriptions
            self.subscribed_sessions.clear()
            # Wait for message task to finish
            message_task.cancel()
            try:
                await message_task
            except asyncio.CancelledError:
                pass

    async def _handle_vague_prompt(self, user_input: str, vagueness: 'VaguenessScore') -> tuple[bool, str]:
        """
        Handle a vague prompt by showing warning and offering improvements.

        Args:
            user_input: The user's prompt
            vagueness: The vagueness analysis result

        Returns:
            tuple: (should_proceed: bool, prompt_to_use: str)
        """
        from rich.table import Table
        from rich.panel import Panel

        console.print()  # Blank line

        # Create severity indicator
        severity_colors = {
            "high": "red",
            "medium": "yellow",
            "low": "blue"
        }
        severity_icons = {
            "high": "🔴",
            "medium": "⚠️",
            "low": "💡"
        }

        severity = vagueness.severity
        color = severity_colors.get(severity, "yellow")
        icon = severity_icons.get(severity, "⚠️")

        # Show vagueness warning
        console.print(f"[bold {color}]{icon} Vague prompt detected (score: {vagueness.score}/100)[/bold {color}]")
        console.print()

        # Show issues
        if vagueness.issues:
            console.print("[bold]Issues:[/bold]")
            for issue in vagueness.issues:
                console.print(f"  • [dim]{issue}[/dim]")
            console.print()

        # Phase 2: Auto-improvement - offer improved prompts
        improvements = None
        if self.enable_prompt_improvement and self.prompt_improver:
            try:
                console.print("[cyan]💡 Generating improved prompts...[/cyan]")
                improvements = self.prompt_improver.improve(user_input)

                if improvements.improvements:
                    console.print()
                    console.print("[bold green]✨ Suggested improvements:[/bold green]")
                    console.print()

                    # Show each improvement
                    for i, imp in enumerate(improvements.improvements[:3], 1):
                        # Create a nice panel for each improvement
                        panel_content = f"[bold]{imp.prompt}[/bold]\n\n"
                        panel_content += f"[dim]{imp.explanation}[/dim]\n"
                        panel_content += f"[dim]Confidence: {imp.confidence}%[/dim]"

                        console.print(Panel(
                            panel_content,
                            title=f"[green]Option {i}[/green]",
                            border_style="green"
                        ))
                        console.print()

            except Exception as e:
                logger.error(f"Failed to generate improvements: {e}")
                # Continue without improvements

        # Ask if user wants to proceed
        if self.session is None:
            # Can't prompt during tests or non-interactive mode
            return (False, user_input)

        try:
            # Offer choices
            if improvements and improvements.improvements:
                console.print("[bold]What would you like to do?[/bold]")
                console.print("  [green]1-3[/green] - Use one of the improved prompts")
                console.print("  [yellow]o[/yellow]   - Proceed with original prompt")
                console.print("  [red]c[/red]   - Cancel")
                console.print()

                response = await self.session.prompt_async(
                    "Your choice: ",
                    multiline=False
                )

                choice = response.strip().lower()

                # Handle numeric choices
                if choice in ['1', '2', '3']:
                    idx = int(choice) - 1
                    if idx < len(improvements.improvements):
                        selected = improvements.improvements[idx]
                        console.print(f"\n[green]✓[/green] Using improved prompt: [bold]{selected.prompt}[/bold]\n")
                        return (True, selected.prompt)

                # Handle 'o' for original
                if choice == 'o':
                    console.print(f"\n[yellow]→[/yellow] Proceeding with original prompt\n")
                    return (True, user_input)

                # Anything else is cancel
                console.print("\n[red]✗[/red] Cancelled\n")
                return (False, user_input)

            else:
                # No improvements available, just ask to proceed
                response = await self.session.prompt_async(
                    "Proceed anyway? (y/n): ",
                    multiline=False
                )

                if response.strip().lower() in ['y', 'yes']:
                    return (True, user_input)
                else:
                    return (False, user_input)

        except (KeyboardInterrupt, EOFError):
            return (False, user_input)

    async def _process_input(self, user_input: str) -> None:
        """
        Process user input.

        Args:
            user_input: The input string from the user
        """
        # 1. Check if it's a CLI command (starts with /)
        if user_input.startswith("/"):
            # Use the command router to handle commands
            await self.router.execute(
                user_input,
                repl_engine=self,
                router=self.router,
                session_manager=self.session_manager,
            )

        # 2. Check if it's a system command (auto-detected from whitelist)
        elif self.system_handler.is_system_command(user_input):
            await self.system_handler.execute(user_input)

        # 3. Default: AI agent message
        else:
            # Regular message - check for vagueness first
            prompt_to_send = user_input  # Default to original prompt

            # Disable vagueness detection for now
            # if self.enable_vagueness_check:
            #     vagueness = self.vagueness_detector.analyze(user_input)

            #     if vagueness.is_vague:
            #         # Show vagueness warning and get improved prompt if available
            #         should_proceed, prompt_to_send = await self._handle_vague_prompt(user_input, vagueness)
            #         if not should_proceed:
            #             return  # User chose not to proceed

            # Regular message - send to agent via broker (use improved prompt if selected)
            success = self.session_manager.send_message(prompt_to_send)
            if success:
                # Block input until agent responds
                self.agent_idle.clear()
            else:
                self.renderer.warning(
                    "No active session. Use '/new [agent-type]' to create a session."
                )

