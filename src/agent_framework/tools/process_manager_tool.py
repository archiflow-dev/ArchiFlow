"""Process manager tool for controlling background processes."""
import psutil
from typing import Dict, Optional
from .tool_base import BaseTool, ToolResult
from .bash_tool import _background_processes


class ProcessManagerTool(BaseTool):
    """Tool for managing background processes started by bash tool.

    This tool allows agents to check status and stop background processes.
    """

    name: str = "process_manager"
    description: str = """Manage background processes started by the bash tool.

    Operations:
    - list: List all running background processes
    - status: Check if a specific process is running
    - stop: Stop a running background process
    - kill: Force kill a background process

    Use this to manage servers, watchers, and other long-running processes."""

    parameters: Dict = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["list", "status", "stop", "kill"],
                "description": "Operation to perform: list, status, stop, or kill"
            },
            "pid": {
                "type": "integer",
                "description": "Process ID (required for status, stop, kill operations)"
            }
        },
        "required": ["operation"]
    }

    async def execute(
        self,
        operation: str,
        pid: Optional[int] = None
    ) -> ToolResult:
        """Execute process management operation.

        Args:
            operation: Operation to perform (list, status, stop, kill)
            pid: Process ID (required for status, stop, kill)

        Returns:
            ToolResult with operation result
        """
        try:
            if operation == "list":
                return self._list_processes()
            elif operation == "status":
                if pid is None:
                    return ToolResult(error="PID required for status operation")
                return self._check_status(pid)
            elif operation == "stop":
                if pid is None:
                    return ToolResult(error="PID required for stop operation")
                return self._stop_process(pid)
            elif operation == "kill":
                if pid is None:
                    return ToolResult(error="PID required for kill operation")
                return self._kill_process(pid)
            else:
                return ToolResult(error=f"Unknown operation: {operation}")

        except Exception as e:
            return ToolResult(
                error=f"Process management error: {type(e).__name__}: {str(e)}"
            )

    def _list_processes(self) -> ToolResult:
        """List all running background processes."""
        if not _background_processes:
            return ToolResult(output="No background processes running.")

        output_lines = ["Background Processes:", "=" * 80]

        for pid, process in _background_processes.items():
            try:
                # Check if process is still running
                if process.poll() is None:
                    # Process is running
                    ps_info = psutil.Process(pid)
                    cpu_percent = ps_info.cpu_percent(interval=0.1)
                    memory_mb = ps_info.memory_info().rss / 1024 / 1024

                    output_lines.append(f"\n[PID {pid}] ✅ RUNNING")
                    output_lines.append(f"  Command: {' '.join(ps_info.cmdline())[:80]}")
                    output_lines.append(f"  CPU: {cpu_percent:.1f}%")
                    output_lines.append(f"  Memory: {memory_mb:.1f} MB")
                    output_lines.append(f"  Working Dir: {ps_info.cwd()}")
                else:
                    # Process has exited
                    output_lines.append(f"\n[PID {pid}] ❌ EXITED")
                    output_lines.append(f"  Exit Code: {process.returncode}")
            except psutil.NoSuchProcess:
                output_lines.append(f"\n[PID {pid}] ❌ NOT FOUND")
            except Exception as e:
                output_lines.append(f"\n[PID {pid}] ⚠️  ERROR: {str(e)}")

        output_lines.append("\n" + "=" * 80)
        return ToolResult(output="\n".join(output_lines))

    def _check_status(self, pid: int) -> ToolResult:
        """Check status of a specific process."""
        if pid not in _background_processes:
            return ToolResult(
                output=f"PID {pid} not found in background processes registry.\n"
                       f"It may not have been started by this agent."
            )

        process = _background_processes[pid]

        try:
            if process.poll() is None:
                # Process is running
                ps_info = psutil.Process(pid)
                cpu_percent = ps_info.cpu_percent(interval=0.1)
                memory_mb = ps_info.memory_info().rss / 1024 / 1024
                status_info = ps_info.status()

                output = f"""Process Status: ✅ RUNNING

PID: {pid}
Status: {status_info}
Command: {' '.join(ps_info.cmdline())}
CPU: {cpu_percent:.1f}%
Memory: {memory_mb:.1f} MB
Working Directory: {ps_info.cwd()}
Create Time: {psutil.datetime.datetime.fromtimestamp(ps_info.create_time())}

The process is running normally."""

                return ToolResult(output=output)
            else:
                # Process has exited
                output = f"""Process Status: ❌ EXITED

PID: {pid}
Exit Code: {process.returncode}

The process has terminated."""

                return ToolResult(output=output)

        except psutil.NoSuchProcess:
            return ToolResult(
                output=f"Process {pid} not found. It may have been terminated."
            )
        except Exception as e:
            return ToolResult(
                error=f"Error checking process status: {type(e).__name__}: {str(e)}"
            )

    def _stop_process(self, pid: int) -> ToolResult:
        """Gracefully stop a process (SIGTERM)."""
        if pid not in _background_processes:
            return ToolResult(
                error=f"PID {pid} not found in background processes registry."
            )

        process = _background_processes[pid]

        try:
            if process.poll() is not None:
                # Process already exited
                output = f"Process {pid} has already exited (exit code: {process.returncode})."
                del _background_processes[pid]
                return ToolResult(output=output)

            # Gracefully terminate
            ps_process = psutil.Process(pid)
            ps_process.terminate()  # Send SIGTERM

            # Wait for termination (up to 5 seconds)
            try:
                ps_process.wait(timeout=5)
                output = f"✅ Process {pid} stopped successfully."
                del _background_processes[pid]
                return ToolResult(output=output)
            except psutil.TimeoutExpired:
                return ToolResult(
                    output=f"⚠️  Process {pid} did not stop within 5 seconds.\n"
                           f"You may need to use 'kill' operation to force stop it."
                )

        except psutil.NoSuchProcess:
            output = f"Process {pid} not found (may have already stopped)."
            if pid in _background_processes:
                del _background_processes[pid]
            return ToolResult(output=output)
        except Exception as e:
            return ToolResult(
                error=f"Error stopping process: {type(e).__name__}: {str(e)}"
            )

    def _kill_process(self, pid: int) -> ToolResult:
        """Force kill a process (SIGKILL)."""
        if pid not in _background_processes:
            return ToolResult(
                error=f"PID {pid} not found in background processes registry."
            )

        process = _background_processes[pid]

        try:
            if process.poll() is not None:
                # Process already exited
                output = f"Process {pid} has already exited (exit code: {process.returncode})."
                del _background_processes[pid]
                return ToolResult(output=output)

            # Force kill
            ps_process = psutil.Process(pid)
            ps_process.kill()  # Send SIGKILL

            # Wait briefly
            try:
                ps_process.wait(timeout=2)
                output = f"✅ Process {pid} killed successfully."
                del _background_processes[pid]
                return ToolResult(output=output)
            except psutil.TimeoutExpired:
                return ToolResult(
                    error=f"Failed to kill process {pid} - it may be in an unkillable state."
                )

        except psutil.NoSuchProcess:
            output = f"Process {pid} not found (may have already stopped)."
            if pid in _background_processes:
                del _background_processes[pid]
            return ToolResult(output=output)
        except Exception as e:
            return ToolResult(
                error=f"Error killing process: {type(e).__name__}: {str(e)}"
            )
