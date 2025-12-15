"""
Tests for the CLI entry point.
"""

from unittest.mock import AsyncMock, patch

from click.testing import CliRunner

from agent_cli.main import cli


def test_cli_version_flag() -> None:
    """Test that --version flag works."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "agent-cli version 0.1.0" in result.output


def test_cli_version_command() -> None:
    """Test that version subcommand works."""
    runner = CliRunner()
    result = runner.invoke(cli, ["version"])
    assert result.exit_code == 0
    assert "agent-cli version 0.1.0" in result.output


def test_cli_help() -> None:
    """Test that --help works."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "AI Agent Framework CLI" in result.output
    assert "Commands:" in result.output


def test_cli_repl_command() -> None:
    """Test that repl subcommand works."""
    runner = CliRunner()
    with patch("agent_cli.repl.engine.REPLEngine.run", new_callable=AsyncMock) as mock_run:
        result = runner.invoke(cli, ["repl"])
        assert result.exit_code == 0
        mock_run.assert_called_once()


def test_cli_default_starts_repl() -> None:
    """Test that running without arguments starts REPL."""
    runner = CliRunner()
    with patch("agent_cli.repl.engine.REPLEngine.run", new_callable=AsyncMock) as mock_run:
        result = runner.invoke(cli, [])
        assert result.exit_code == 0
        mock_run.assert_called_once()
