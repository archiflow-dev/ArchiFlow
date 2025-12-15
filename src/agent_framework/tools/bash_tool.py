"""Bash command execution tool for agents."""
import subprocess
import os
from typing import Dict, Optional, List
from pydantic import Field
from .tool_base import BaseTool, ToolResult


class BashTool(BaseTool):
    """Tool for executing bash/shell commands.

    This tool allows agents to run shell commands and capture their output.
    Use with caution as it can execute arbitrary commands.
    """

    name: str = "bash"
    description: str = "Execute bash/shell commands and return the output. Use this to run system commands, scripts, or interact with the file system."

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
                "description": "Command timeout in seconds. Defaults to 30 seconds.",
                "default": 30
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

    async def execute(
        self,
        command: str,
        working_directory: str = None,
        timeout: int = 30
    ) -> ToolResult:
        """Execute a bash command and return the result.

        Args:
            command: The bash command to execute
            working_directory: Optional directory to run the command in
            timeout: Timeout in seconds (capped at max_timeout)

        Returns:
            ToolResult with the command output or error
        """
        try:
            # Validate command is allowed
            if not self._is_command_allowed(command):
                return ToolResult(
                    error=f"Command '{command}' is not allowed. Allowed commands: {self.allowed_commands}"
                )

            # Cap timeout at max_timeout
            timeout = min(timeout, self.max_timeout)

            # Validate working directory if provided
            if working_directory and not os.path.isdir(working_directory):
                return ToolResult(
                    error=f"Working directory does not exist: {working_directory}"
                )

            # Determine the shell to use
            shell = True  # Use shell to interpret commands

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
