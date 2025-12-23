"""Tests for background process management in BashTool and ProcessManagerTool."""
import pytest
import asyncio
import time
from agent_framework.tools.bash_tool import BashTool, _background_processes
from agent_framework.tools.process_manager_tool import ProcessManagerTool


@pytest.mark.asyncio
class TestBackgroundProcessManagement:
    """Test suite for background process management."""

    async def test_long_running_detection(self):
        """Test that long-running commands are detected."""
        tool = BashTool()

        # Should detect servers
        assert tool._is_long_running_command("python -m http.server 8000")
        assert tool._is_long_running_command("flask run")
        assert tool._is_long_running_command("uvicorn app:app")
        assert tool._is_long_running_command("npm start")
        assert tool._is_long_running_command("npm run dev")
        assert tool._is_long_running_command("nodemon server.js")

        # Should NOT detect regular commands
        assert not tool._is_long_running_command("ls -la")
        assert not tool._is_long_running_command("python script.py")
        assert not tool._is_long_running_command("npm install")
        assert not tool._is_long_running_command("pytest")

    async def test_warning_without_background_flag(self):
        """Test that warning appears when trying to run server without background=True."""
        tool = BashTool()

        # Try to run server without background flag
        result = await tool.execute(
            command="python -m http.server 8000",
            background=False
        )

        # Should get warning error
        assert result.error is not None
        assert "WARNING" in result.error
        assert "long-running command" in result.error
        assert "background=True" in result.error

    async def test_background_execution_simple(self):
        """Test starting a simple background process."""
        tool = BashTool()

        # Start a long-running sleep command in background
        result = await tool.execute(
            command="python -c \"import time; time.sleep(100)\"",
            background=True
        )

        # Should succeed
        assert result.error is None
        assert "Background process started" in result.output
        assert "PID" in result.output

        # Extract PID from output
        import re
        match = re.search(r'PID:\s*(\d+)', result.output)
        assert match is not None
        pid = int(match.group(1))

        # Verify process is in registry
        assert pid in _background_processes

        # Clean up - stop the process
        pm_tool = ProcessManagerTool()
        stop_result = await pm_tool.execute(operation="stop", pid=pid)
        assert "stopped successfully" in stop_result.output or "exited" in stop_result.output

    async def test_process_manager_list(self):
        """Test listing background processes."""
        tool = BashTool()
        pm_tool = ProcessManagerTool()

        # Start two background processes
        result1 = await tool.execute(
            command="python -c \"import time; time.sleep(100)\"",
            background=True
        )
        result2 = await tool.execute(
            command="python -c \"import time; time.sleep(100)\"",
            background=True
        )

        # Extract PIDs
        import re
        pid1 = int(re.search(r'PID:\s*(\d+)', result1.output).group(1))
        pid2 = int(re.search(r'PID:\s*(\d+)', result2.output).group(1))

        # List processes
        list_result = await pm_tool.execute(operation="list")
        assert list_result.error is None
        assert str(pid1) in list_result.output
        assert str(pid2) in list_result.output
        assert "RUNNING" in list_result.output

        # Clean up
        await pm_tool.execute(operation="stop", pid=pid1)
        await pm_tool.execute(operation="stop", pid=pid2)

    async def test_process_manager_status(self):
        """Test checking process status."""
        tool = BashTool()
        pm_tool = ProcessManagerTool()

        # Start background process
        result = await tool.execute(
            command="python -c \"import time; time.sleep(100)\"",
            background=True
        )

        import re
        pid = int(re.search(r'PID:\s*(\d+)', result.output).group(1))

        # Check status
        status_result = await pm_tool.execute(operation="status", pid=pid)
        assert status_result.error is None
        assert "RUNNING" in status_result.output
        assert "CPU" in status_result.output
        assert "Memory" in status_result.output

        # Clean up
        await pm_tool.execute(operation="stop", pid=pid)

    async def test_process_manager_stop(self):
        """Test stopping a background process."""
        tool = BashTool()
        pm_tool = ProcessManagerTool()

        # Start background process
        result = await tool.execute(
            command="python -c \"import time; time.sleep(100)\"",
            background=True
        )

        import re
        pid = int(re.search(r'PID:\s*(\d+)', result.output).group(1))

        # Verify it's running
        status_before = await pm_tool.execute(operation="status", pid=pid)
        assert "RUNNING" in status_before.output

        # Stop it
        stop_result = await pm_tool.execute(operation="stop", pid=pid)
        assert stop_result.error is None
        assert "stopped successfully" in stop_result.output

        # Verify it's no longer in registry
        assert pid not in _background_processes

    async def test_background_prevents_timeout(self):
        """Test that background mode prevents timeout on long commands."""
        tool = BashTool()

        # This would timeout in foreground mode (default timeout 30s)
        # But should succeed immediately in background mode
        start_time = time.time()

        result = await tool.execute(
            command="python -c \"import time; time.sleep(60)\"",  # 60 seconds
            background=True,
            timeout=5  # Low timeout - would fail in foreground
        )

        elapsed = time.time() - start_time

        # Should return almost immediately (< 2 seconds)
        assert elapsed < 2
        assert result.error is None
        assert "Background process started" in result.output

        # Clean up
        import re
        pid = int(re.search(r'PID:\s*(\d+)', result.output).group(1))
        pm_tool = ProcessManagerTool()
        await pm_tool.execute(operation="stop", pid=pid)

    async def test_pattern_matching_comprehensive(self):
        """Test comprehensive pattern matching for various server types."""
        tool = BashTool()

        # Web servers
        assert tool._is_long_running_command("python -m http.server 8000")
        assert tool._is_long_running_command("python server.py")
        assert tool._is_long_running_command("flask run --port 5000")
        assert tool._is_long_running_command("uvicorn main:app --reload")
        assert tool._is_long_running_command("gunicorn app:app")

        # Node.js
        assert tool._is_long_running_command("npm start")
        assert tool._is_long_running_command("npm run dev")
        assert tool._is_long_running_command("yarn start")
        assert tool._is_long_running_command("yarn dev")
        assert tool._is_long_running_command("node server.js")
        assert tool._is_long_running_command("nodemon app.js")

        # Frontend frameworks
        assert tool._is_long_running_command("ng serve")
        assert tool._is_long_running_command("gatsby develop")
        assert tool._is_long_running_command("next dev")
        assert tool._is_long_running_command("vite")

        # Docker
        assert tool._is_long_running_command("docker run postgres")
        assert tool._is_long_running_command("docker run -p 5432:5432 postgres")
        assert not tool._is_long_running_command("docker run -d postgres")  # -d is detached

        # Watchers
        assert tool._is_long_running_command("watch pytest")
        assert tool._is_long_running_command("webpack-dev-server")

        # Static file servers (npx commands)
        assert tool._is_long_running_command("npx http-server -p 8000")
        assert tool._is_long_running_command("npx http-server -p 8000 --cors")
        assert tool._is_long_running_command("npx serve")
        assert tool._is_long_running_command("npx live-server")
        assert tool._is_long_running_command("http-server -p 8000")
        assert tool._is_long_running_command("serve dist/")
        assert tool._is_long_running_command("live-server --port=8080")

        # Should NOT match normal commands
        assert not tool._is_long_running_command("python test.py")
        assert not tool._is_long_running_command("npm install")
        assert not tool._is_long_running_command("docker ps")
        assert not tool._is_long_running_command("ls -la")
        assert not tool._is_long_running_command("npx create-react-app myapp")  # Not a server
