"""Bash command execution tool for agents."""
import subprocess
import os
import re
import threading
import queue
from typing import Dict, Optional, List, ClassVar
from pydantic import Field
from .tool_base import BaseTool, ToolResult

# Global registry of background processes
_background_processes: Dict[int, subprocess.Popen] = {}


class BashTool(BaseTool):
    """Tool for executing bash/shell commands.

    This tool allows agents to run shell commands and capture their output.
    Use with caution as it can execute arbitrary commands.

    For long-running processes (servers, watchers), use background=True to run
    the process in the background and get immediate control back.
    """

    name: str = "bash"
    description: str = """Execute bash/shell commands and return the output.

    IMPORTANT: For long-running processes (servers, watchers, daemons), set background=True
    to run the command in the background. Examples:
    - python -m http.server 8000 (use background=True)
    - npx http-server -p 8000 (use background=True)
    - npm start (use background=True)
    - flask run (use background=True)
    - uvicorn app:app (use background=True)
    - python server.py (use background=True)

    The tool will detect common server patterns and warn you if background mode is recommended."""

    # Patterns for detecting long-running commands (ClassVar to avoid Pydantic field)
    LONG_RUNNING_PATTERNS: ClassVar[List[str]] = [
        r'python\s+-m\s+http\.server',
        r'python\s+.*server\.py',
        r'flask\s+run',
        r'uvicorn\s+',
        r'gunicorn\s+',
        r'npm\s+(start|run\s+dev)',
        r'yarn\s+(start|dev)',
        r'ng\s+serve',
        r'gatsby\s+develop',
        r'next\s+dev',
        r'vite(\s+|$)',             # vite (with or without args)
        r'webpack-dev-server',
        r'node\s+.*server\.js',
        r'docker\s+run(?!\s+-d)',   # docker run without -d (detached)
        r'watch\s+',
        r'nodemon\s+',
        r'npx\s+http-server',       # npx http-server
        r'npx\s+serve',             # npx serve
        r'npx\s+live-server',       # npx live-server
        r'http-server(\s+|$)',      # http-server (with or without args)
        r'live-server(\s+|$)',      # live-server (with or without args)
        r'serve(\s+|$)',            # serve command (with or without args)
    ]

    parameters: Dict = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The bash command to execute (e.g., 'ls -la', 'pwd', 'cat file.txt')"
            },
            "working_directory": {
                "type": "string",
                "description": "Optional working directory to execute the command in. Defaults to current directory."
            },
            "timeout": {
                "type": "integer",
                "description": "Command timeout in seconds. Defaults to 30 seconds. Ignored if background=True.",
                "default": 30
            },
            "background": {
                "type": "boolean",
                "description": "Run command in background (for servers, watchers, etc.). Returns immediately with PID.",
                "default": False
            }
        },
        "required": ["command"]
    }

    # Configuration fields
    allowed_commands: Optional[List[str]] = Field(
        default=None,
        description="Optional list of allowed command prefixes"
    )
    max_timeout: int = Field(
        default=300,
        description="Maximum allowed timeout in seconds"
    )

    def _is_command_allowed(self, command: str) -> bool:
        """Check if a command is allowed based on the whitelist."""
        if self.allowed_commands is None:
            return True

        # Extract the base command (first word)
        base_command = command.strip().split()[0]

        # Check if the base command starts with any allowed prefix
        return any(base_command.startswith(allowed) for allowed in self.allowed_commands)

    def _is_long_running_command(self, command: str) -> bool:
        """Detect if command is likely a long-running process (server, watcher, etc.)."""
        for pattern in self.LONG_RUNNING_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return True
        return False

    async def execute(
        self,
        command: str,
        working_directory: str = None,
        timeout: int = 30,
        background: bool = False
    ) -> ToolResult:
        """Execute a bash command and return the result.

        Args:
            command: The bash command to execute
            working_directory: Optional directory to run the command in.
                              Defaults to execution context's working directory if set.
            timeout: Timeout in seconds (capped at max_timeout)
            background: Run command in background (for long-running processes)

        Returns:
            ToolResult with the command output or error
        """
        try:
            # Validate command is allowed
            if not self._is_command_allowed(command):
                return ToolResult(
                    error=f"Command '{command}' is not allowed. Allowed commands: {self.allowed_commands}"
                )

            # Detect long-running command and warn if not using background mode
            is_long_running = self._is_long_running_command(command)
            if is_long_running and not background:
                warning_msg = (
                    f"⚠️  WARNING: Detected long-running command pattern!\n"
                    f"Command: {command}\n\n"
                    f"This appears to be a server/watcher that runs indefinitely.\n"
                    f"RECOMMENDATION: Use background=True to run it in the background.\n\n"
                    f"Example: bash(command=\"{command}\", background=True)\n\n"
                    f"Proceeding with foreground execution (will timeout after {timeout}s)..."
                )
                return ToolResult(
                    error=warning_msg
                )

            # Cap timeout at max_timeout
            timeout = min(timeout, self.max_timeout)

            # Use execution context's working directory as default
            if working_directory is None:
                working_directory = self.get_working_directory()
            elif working_directory:
                # Resolve relative working directory paths
                working_directory = self.resolve_path(working_directory)

            # Validate working directory if provided
            if working_directory and not os.path.isdir(working_directory):
                return ToolResult(
                    error=f"Working directory does not exist: {working_directory}"
                )

            # Determine the shell to use
            shell = True  # Use shell to interpret commands

            # BACKGROUND EXECUTION
            if background:
                return self._execute_background(command, working_directory)

            # FOREGROUND EXECUTION
            # Execute the command
            result = subprocess.run(
                command,
                shell=shell,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=working_directory,
                env=os.environ.copy()
            )

            # Prepare output
            output_parts = []

            if result.stdout:
                output_parts.append(f"STDOUT:\n{result.stdout}")

            if result.stderr:
                output_parts.append(f"STDERR:\n{result.stderr}")

            output = "\n\n".join(output_parts) if output_parts else "(no output)"

            # Add return code info
            output += f"\n\nReturn Code: {result.returncode}"

            # Check if command succeeded
            if result.returncode != 0:
                return ToolResult(
                    output=output,
                    error=f"Command exited with non-zero status: {result.returncode} \n Details: \n {output}"
                )

            return ToolResult(output=output)

        except subprocess.TimeoutExpired:
            return ToolResult(
                error=f"Command timed out after {timeout} seconds"
            )
        except FileNotFoundError as e:
            return ToolResult(
                error=f"Command not found: {str(e)}"
            )
        except PermissionError as e:
            return ToolResult(
                error=f"Permission denied: {str(e)}"
            )
        except Exception as e:
            return ToolResult(
                error=f"Error executing command: {type(e).__name__}: {str(e)}"
            )

    def _execute_background(self, command: str, working_directory: str = None) -> ToolResult:
        """Execute command in background and return immediately with PID.

        Args:
            command: Command to execute
            working_directory: Working directory for the process

        Returns:
            ToolResult with process information
        """
        try:
            # Start process in background
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=working_directory,
                env=os.environ.copy()
            )

            # Register in global registry
            _background_processes[process.pid] = process

            # Collect initial output (wait briefly for startup messages)
            import time
            time.sleep(0.5)  # Give process time to start

            # Try to read any initial output (non-blocking)
            try:
                import select
                # For Windows compatibility, we'll skip non-blocking read
                initial_output = "(Process started - check logs for output)"
            except:
                initial_output = "(Process started - check logs for output)"

            output = f"""✅ Background process started successfully!

Process ID (PID): {process.pid}
Command: {command}
Working Directory: {working_directory or '(current)'}

{initial_output}

To manage this process:
- Check if running: Use process_status tool with PID {process.pid}
- Stop the process: Use stop_process tool with PID {process.pid}
- View logs: Check application logs or use ps/tasklist commands

NOTE: The process will continue running in the background.
Remember to stop it when done to free up resources."""

            return ToolResult(output=output)

        except Exception as e:
            return ToolResult(
                error=f"Failed to start background process: {type(e).__name__}: {str(e)}"
            )


class RestrictedBashTool(BashTool):
    """A restricted version of BashTool with safe defaults.

    Only allows common read-only and safe commands.
    """

    # Override defaults with safe values
    allowed_commands: List[str] = Field(
        default=[
            'ls', 'cat', 'pwd', 'echo', 'head', 'tail',
            'grep', 'find', 'wc', 'which', 'whoami',
            'date', 'env', 'python', 'pip', 'git'
        ],
        description="Safe read-only commands"
    )
    max_timeout: int = Field(
        default=60,
        description="Maximum timeout for restricted tool"
    )
