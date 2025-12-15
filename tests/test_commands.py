"""
Tests for the command system.
"""

import pytest

from agent_cli.commands.router import CommandRouter
from agent_cli.commands.utility import register_utility_commands
from agent_cli.repl.engine import REPLEngine


@pytest.mark.asyncio
async def test_router_register_command() -> None:
    """Test registering a command."""
    router = CommandRouter()

    async def test_handler() -> None:
        pass

    router.register("test", test_handler, "Test command")
    assert router.get_command("test") is not None
    assert router.get_command("test").name == "test"  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_router_unregister_command() -> None:
    """Test unregistering a command."""
    router = CommandRouter()

    async def test_handler() -> None:
        pass

    router.register("test", test_handler, "Test command")
    router.unregister("test")
    assert router.get_command("test") is None


@pytest.mark.asyncio
async def test_router_list_commands() -> None:
    """Test listing commands."""
    router = CommandRouter()

    async def handler1() -> None:
        pass

    async def handler2() -> None:
        pass

    router.register("cmd1", handler1, "Command 1")
    router.register("cmd2", handler2, "Command 2")

    commands = router.list_commands()
    assert len(commands) == 2
    assert commands[0].name == "cmd1"
    assert commands[1].name == "cmd2"


@pytest.mark.asyncio
async def test_router_parse_command() -> None:
    """Test parsing commands."""
    router = CommandRouter()

    # Simple command
    result = router.parse_command("/help")
    assert result is not None
    assert result[0] == "help"
    assert result[1] == []

    # Command with arguments
    result = router.parse_command("/echo hello world")
    assert result is not None
    assert result[0] == "echo"
    assert result[1] == ["hello", "world"]

    # Command with quoted arguments
    result = router.parse_command('/echo "hello world" test')
    assert result is not None
    assert result[0] == "echo"
    assert result[1] == ["hello world", "test"]

    # Not a command
    result = router.parse_command("not a command")
    assert result is None


@pytest.mark.asyncio
async def test_router_execute_command() -> None:
    """Test executing a command."""
    router = CommandRouter()
    executed = []

    async def test_handler() -> None:
        executed.append(True)

    router.register("test", test_handler, "Test command")

    result = await router.execute("/test")
    assert result is True
    assert len(executed) == 1


@pytest.mark.asyncio
async def test_router_execute_with_args() -> None:
    """Test executing command with arguments."""
    router = CommandRouter()
    captured_args = []

    async def test_handler(*args: str) -> None:
        captured_args.extend(args)

    router.register("test", test_handler, "Test command")

    await router.execute("/test arg1 arg2")
    assert captured_args == ["arg1", "arg2"]


@pytest.mark.asyncio
async def test_router_execute_unknown_command() -> None:
    """Test executing unknown command."""
    router = CommandRouter()

    result = await router.execute("/unknown")
    assert result is False


@pytest.mark.asyncio
async def test_utility_commands_registered() -> None:
    """Test that utility commands are registered."""
    router = CommandRouter()
    register_utility_commands(router)

    assert router.get_command("help") is not None
    assert router.get_command("exit") is not None
    assert router.get_command("quit") is not None
    assert router.get_command("clear") is not None
    assert router.get_command("version") is not None


@pytest.mark.asyncio
async def test_help_command() -> None:
    """Test help command execution."""
    router = CommandRouter()
    register_utility_commands(router)

    # Should not raise
    await router.execute("/help", router=router)


@pytest.mark.asyncio
async def test_exit_command() -> None:
    """Test exit command execution."""
    router = CommandRouter()
    register_utility_commands(router)
    repl = REPLEngine()
    repl.running = True

    await router.execute("/exit", repl_engine=repl)
    assert repl.running is False


@pytest.mark.asyncio
async def test_quit_command() -> None:
    """Test quit command (alias for exit)."""
    router = CommandRouter()
    register_utility_commands(router)
    repl = REPLEngine()
    repl.running = True

    await router.execute("/quit", repl_engine=repl)
    assert repl.running is False


@pytest.mark.asyncio
async def test_clear_command() -> None:
    """Test clear command execution."""
    router = CommandRouter()
    register_utility_commands(router)

    # Should not raise
    await router.execute("/clear")


@pytest.mark.asyncio
async def test_version_command() -> None:
    """Test version command execution."""
    router = CommandRouter()
    register_utility_commands(router)

    # Should not raise
    await router.execute("/version")


@pytest.mark.asyncio
async def test_repl_uses_router() -> None:
    """Test that REPL engine uses command router."""
    repl = REPLEngine()

    # Router should be initialized
    assert repl.router is not None

    # Utility commands should be registered
    assert repl.router.get_command("help") is not None
    assert repl.router.get_command("exit") is not None


@pytest.mark.asyncio
async def test_repl_process_command() -> None:
    """Test REPL processing commands via router."""
    repl = REPLEngine()
    repl.running = True

    # Execute exit command
    await repl._process_input("/exit")

    # Should have stopped
    assert repl.running is False
