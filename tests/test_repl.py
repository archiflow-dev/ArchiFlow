"""
Tests for the REPL engine.
"""

import pytest

from agent_cli.repl.engine import REPLEngine


@pytest.mark.asyncio
async def test_repl_engine_init() -> None:
    """Test REPL engine initialization."""
    repl = REPLEngine()
    assert repl.config_path is None
    assert repl.running is False
    assert repl.history is not None
    assert repl.session is None  # Session is lazily initialized
    assert repl.router is not None  # Router should be initialized


@pytest.mark.asyncio
async def test_repl_engine_init_with_config() -> None:
    """Test REPL engine initialization with config path."""
    from pathlib import Path

    config_path = Path("/tmp/config.yaml")
    repl = REPLEngine(config_path=config_path)
    assert repl.config_path == config_path


@pytest.mark.asyncio
async def test_process_regular_input() -> None:
    """Test processing regular user input."""
    repl = REPLEngine()
    # Should not raise any errors
    await repl._process_input("Hello, agent!")


@pytest.mark.asyncio
async def test_handle_exit_command() -> None:
    """Test /exit command."""
    repl = REPLEngine()
    repl.running = True
    await repl._process_input("/exit")
    assert repl.running is False


@pytest.mark.asyncio
async def test_handle_quit_command() -> None:
    """Test /quit command."""
    repl = REPLEngine()
    repl.running = True
    await repl._process_input("/quit")
    assert repl.running is False


@pytest.mark.asyncio
async def test_handle_help_command() -> None:
    """Test /help command."""
    repl = REPLEngine()
    # Should not raise any errors
    await repl._process_input("/help")


@pytest.mark.asyncio
async def test_handle_version_command() -> None:
    """Test /version command."""
    repl = REPLEngine()
    # Should not raise any errors
    await repl._process_input("/version")


@pytest.mark.asyncio
async def test_handle_clear_command() -> None:
    """Test /clear command."""
    repl = REPLEngine()
    # Should not raise any errors
    await repl._process_input("/clear")


@pytest.mark.asyncio
async def test_handle_unknown_command() -> None:
    """Test handling unknown command."""
    repl = REPLEngine()
    # Should not raise any errors
    await repl._process_input("/unknown")


@pytest.mark.asyncio
async def test_process_slash_command() -> None:
    """Test that slash commands are routed correctly."""
    repl = REPLEngine()
    repl.running = True
    await repl._process_input("/exit")
    assert repl.running is False
