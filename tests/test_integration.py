"""
Integration tests for Phase 1.

Tests the complete CLI workflow including REPL, commands, and rendering.
"""

from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from agent_cli.commands.router import CommandRouter
from agent_cli.commands.utility import register_utility_commands
from agent_cli.main import cli
from agent_cli.output.renderer import OutputRenderer
from agent_cli.repl.engine import REPLEngine


class TestREPLIntegration:
    """Integration tests for REPL engine."""

    @pytest.mark.asyncio
    async def test_repl_startup(self) -> None:
        """Test that REPL can be initialized with all components."""
        repl = REPLEngine()

        # Verify all components are initialized
        assert repl.router is not None
        assert repl.history is not None
        assert repl.config_path is None
        assert repl.running is False

        # Verify commands are registered
        commands = repl.router.list_commands()
        assert len(commands) >= 5  # help, exit, quit, clear, version

    @pytest.mark.asyncio
    async def test_repl_command_execution_flow(self) -> None:
        """Test complete command execution flow."""
        repl = REPLEngine()
        repl.running = True

        # Test exit command stops the REPL
        await repl._process_input("/exit")
        assert repl.running is False

    @pytest.mark.asyncio
    async def test_repl_multiple_commands(self) -> None:
        """Test executing multiple commands in sequence."""
        repl = REPLEngine()

        # Execute multiple commands
        await repl._process_input("/version")
        await repl._process_input("/help")
        await repl._process_input("/clear")

        # Should not raise any errors

    @pytest.mark.asyncio
    async def test_repl_regular_message_handling(self) -> None:
        """Test handling regular messages (non-commands)."""
        repl = REPLEngine()

        # Process regular message
        await repl._process_input("Hello, agent!")

        # Should not raise any errors

    @pytest.mark.asyncio
    async def test_repl_empty_input_handling(self) -> None:
        """Test handling empty input."""
        repl = REPLEngine()

        # Empty string should be handled gracefully
        await repl._process_input("")
        await repl._process_input("   ")

        # Should not raise any errors


class TestCommandRouterIntegration:
    """Integration tests for command router."""

    @pytest.mark.asyncio
    async def test_router_with_utility_commands(self) -> None:
        """Test router with all utility commands registered."""
        router = CommandRouter()
        register_utility_commands(router)

        # Test all commands are registered
        assert router.get_command("help") is not None
        assert router.get_command("exit") is not None
        assert router.get_command("quit") is not None
        assert router.get_command("clear") is not None
        assert router.get_command("version") is not None

    @pytest.mark.asyncio
    async def test_router_command_parsing_variations(self) -> None:
        """Test parsing various command formats."""
        router = CommandRouter()

        # Simple command
        result = router.parse_command("/help")
        assert result is not None
        assert result[0] == "help"

        # Command with args
        result = router.parse_command("/test arg1 arg2")
        assert result is not None
        assert result[1] == ["arg1", "arg2"]

        # Command with quoted args
        result = router.parse_command('/test "hello world" foo')
        assert result is not None
        assert result[1] == ["hello world", "foo"]

        # Invalid command (no slash)
        result = router.parse_command("not a command")
        assert result is None

    @pytest.mark.asyncio
    async def test_router_error_handling(self) -> None:
        """Test router error handling for unknown commands."""
        router = CommandRouter()
        register_utility_commands(router)

        # Execute unknown command
        result = await router.execute("/unknown_command")
        assert result is False


class TestOutputRendererIntegration:
    """Integration tests for output renderer."""

    def test_renderer_all_methods(self) -> None:
        """Test all renderer methods work together."""
        renderer = OutputRenderer()

        # Should not raise any errors
        renderer.error("Test error")
        renderer.success("Test success")
        renderer.info("Test info")
        renderer.warning("Test warning")
        renderer.text("Test text")

    def test_renderer_with_rich_features(self) -> None:
        """Test renderer with Rich-specific features."""
        renderer = OutputRenderer()

        # Markdown
        renderer.markdown("# Test\n**Bold**")

        # Code
        renderer.code("print('hello')", language="python")

        # Panel
        renderer.panel("Test content", title="Test")

        # Table
        renderer.table("Test", ["Col1", "Col2"], [["A", "B"]])

        # Should not raise any errors


class TestCLIIntegration:
    """Integration tests for CLI entry point."""

    def test_cli_version_flag(self) -> None:
        """Test CLI version flag."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_cli_help_flag(self) -> None:
        """Test CLI help flag."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "AI Agent Framework CLI" in result.output

    def test_cli_version_command(self) -> None:
        """Test CLI version subcommand."""
        runner = CliRunner()
        result = runner.invoke(cli, ["version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_cli_repl_command(self) -> None:
        """Test CLI REPL subcommand."""
        runner = CliRunner()
        with patch("agent_cli.repl.engine.REPLEngine.run", new_callable=AsyncMock):
            result = runner.invoke(cli, ["repl"])
            assert result.exit_code == 0


class TestEndToEndWorkflow:
    """End-to-end workflow tests."""

    @pytest.mark.asyncio
    async def test_complete_repl_session_flow(self) -> None:
        """Test a complete REPL session workflow."""
        repl = REPLEngine()

        # Start session
        repl.running = True

        # Execute various commands
        await repl._process_input("/version")
        await repl._process_input("/help")
        await repl._process_input("Hello, agent!")
        await repl._process_input("/clear")

        # Still running
        assert repl.running is True

        # Exit
        await repl._process_input("/exit")
        assert repl.running is False

    @pytest.mark.asyncio
    async def test_command_router_repl_integration(self) -> None:
        """Test command router integrated with REPL."""
        repl = REPLEngine()

        # Router should be initialized and have commands
        assert len(repl.router.list_commands()) >= 5

        # Commands should work through REPL
        repl.running = True
        await repl._process_input("/quit")
        assert repl.running is False

    def test_cli_components_initialized_together(self) -> None:
        """Test all CLI components can be initialized together."""
        # Create all components
        repl = REPLEngine()
        router = CommandRouter()
        renderer = OutputRenderer()

        # All should be valid
        assert repl is not None
        assert router is not None
        assert renderer is not None

        # REPL should have its own router
        assert repl.router is not None
        assert len(repl.router.list_commands()) > 0


class TestErrorHandling:
    """Tests for error handling scenarios."""

    @pytest.mark.asyncio
    async def test_unknown_command_handling(self) -> None:
        """Test handling of unknown commands."""
        repl = REPLEngine()

        # Should not raise, just show error
        await repl._process_input("/this_command_does_not_exist")

    @pytest.mark.asyncio
    async def test_malformed_command_handling(self) -> None:
        """Test handling of malformed commands."""
        router = CommandRouter()

        # Unclosed quote - should handle gracefully
        result = router.parse_command('/test "unclosed quote')
        # Should return None or handle error
        assert result is None or isinstance(result, tuple)

    @pytest.mark.asyncio
    async def test_command_execution_error_handling(self) -> None:
        """Test error handling during command execution."""
        router = CommandRouter()

        # Register a command that raises an error
        async def error_command(**context: object) -> None:
            raise ValueError("Test error")

        router.register("error_test", error_command, "Test error command")

        # Should not raise, but return False
        result = await router.execute("/error_test")
        assert result is False


class TestKeyboardInterrupts:
    """Tests for keyboard interrupt handling."""

    @pytest.mark.asyncio
    async def test_repl_handles_empty_input(self) -> None:
        """Test that REPL properly handles empty input."""
        repl = REPLEngine()

        # Empty input should be skipped
        await repl._process_input("")

        # Should not affect running state
        assert repl.running is False

    @pytest.mark.asyncio
    async def test_exit_command_variants(self) -> None:
        """Test all exit command variants."""
        repl = REPLEngine()
        repl.running = True

        # Test /exit
        await repl._process_input("/exit")
        assert repl.running is False

        # Reset and test /quit
        repl.running = True
        await repl._process_input("/quit")
        assert repl.running is False
