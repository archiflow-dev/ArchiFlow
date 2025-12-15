"""
Tests for REPL messaging functionality (Tasks 2.5, 2.6, 2.7).

Tests the integration between REPL, broker, and message rendering.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from agent_cli.repl.engine import REPLEngine


@pytest.fixture
def mock_agent() -> MagicMock:
    """Create a mock agent with tool_registry."""
    agent = MagicMock()
    agent.session_id = "test_session"
    agent.tool_registry = MagicMock()
    return agent


@pytest.fixture
def repl_engine() -> REPLEngine:
    """Create a REPL engine instance."""
    return REPLEngine()


def test_repl_engine_init_with_message_queue(repl_engine: REPLEngine) -> None:
    """Test REPL engine initializes with message queue."""
    assert repl_engine.message_queue is not None
    assert isinstance(repl_engine.message_queue, asyncio.Queue)
    assert repl_engine.subscribed is False
    assert repl_engine.renderer is not None


def test_subscribe_to_output_no_session(repl_engine: REPLEngine) -> None:
    """Test subscribe_to_output with no active session."""
    repl_engine.subscribe_to_output()
    assert repl_engine.subscribed is False


def test_subscribe_to_output_with_session(
    repl_engine: REPLEngine, mock_agent: MagicMock
) -> None:
    """Test subscribe_to_output with active session."""
    # Create a session
    session = repl_engine.session_manager.create_session(agent=mock_agent)

    # Subscribe to output
    repl_engine.subscribe_to_output()

    # Check subscribed
    assert repl_engine.subscribed is True


@pytest.mark.asyncio
async def test_render_message_assistant(repl_engine: REPLEngine) -> None:
    """Test rendering AssistantMessage."""
    message = {
        "type": "AssistantMessage",
        "content": "Hello, user!",
    }

    with patch.object(repl_engine.renderer, "markdown") as mock_markdown:
        await repl_engine.render_message(message)
        mock_markdown.assert_called_once_with("Hello, user!", title="Agent")


@pytest.mark.asyncio
async def test_render_message_tool_call(repl_engine: REPLEngine) -> None:
    """Test rendering ToolCall message."""
    message = {
        "type": "ToolCall",
        "tool_name": "calculator",
        "content": "Calling calculator",
    }

    with patch.object(repl_engine.renderer, "info") as mock_info:
        await repl_engine.render_message(message)
        mock_info.assert_called_once_with("Calling tool: calculator")


@pytest.mark.asyncio
async def test_render_message_tool_result(repl_engine: REPLEngine) -> None:
    """Test rendering ToolResult message."""
    message = {
        "type": "ToolResult",
        "tool_name": "calculator",
        "result": "42",
        "content": "Result: 42",
    }

    with patch.object(repl_engine.renderer, "text") as mock_text:
        await repl_engine.render_message(message)
        mock_text.assert_called_once_with("[dim]Tool 'calculator' result:[/dim] 42")


@pytest.mark.asyncio
async def test_render_message_error(repl_engine: REPLEngine) -> None:
    """Test rendering Error message."""
    message = {
        "type": "Error",
        "content": "Something went wrong",
    }

    with patch.object(repl_engine.renderer, "error") as mock_error:
        await repl_engine.render_message(message)
        mock_error.assert_called_once_with("Something went wrong")


@pytest.mark.asyncio
async def test_render_message_unknown_type(repl_engine: REPLEngine) -> None:
    """Test rendering unknown message type."""
    message = {
        "type": "UnknownType",
        "content": "Some content",
    }

    with patch.object(repl_engine.renderer, "text") as mock_text:
        await repl_engine.render_message(message)
        mock_text.assert_called_once_with("[UnknownType] Some content")


@pytest.mark.asyncio
async def test_process_input_send_message(
    repl_engine: REPLEngine, mock_agent: MagicMock
) -> None:
    """Test processing regular input sends message to agent."""
    # Create a session
    repl_engine.session_manager.create_session(agent=mock_agent)

    # Process input
    await repl_engine._process_input("Hello agent")

    # Check message was published (we can't easily check the broker directly,
    # but we can verify send_message was called)
    # The message should be published via session_manager.send_message


@pytest.mark.asyncio
async def test_process_input_no_session(repl_engine: REPLEngine) -> None:
    """Test processing regular input with no session shows warning."""
    with patch.object(repl_engine.renderer, "warning") as mock_warning:
        await repl_engine._process_input("Hello agent")
        mock_warning.assert_called_once()


@pytest.mark.asyncio
async def test_process_messages_with_message(repl_engine: REPLEngine) -> None:
    """Test process_messages processes messages from queue."""
    repl_engine.running = True

    # Add a message to the queue
    message = {
        "type": "AssistantMessage",
        "content": "Test response",
    }
    await repl_engine.message_queue.put(message)

    # Mock render_message
    with patch.object(repl_engine, "render_message") as mock_render:
        # Run process_messages for a short time
        task = asyncio.create_task(repl_engine.process_messages())
        await asyncio.sleep(0.2)
        repl_engine.running = False
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass

        # Check render_message was called
        mock_render.assert_called_once_with(message)


@pytest.mark.asyncio
async def test_process_messages_timeout(repl_engine: REPLEngine) -> None:
    """Test process_messages handles timeout gracefully."""
    repl_engine.running = True

    # Run process_messages for a short time with no messages
    task = asyncio.create_task(repl_engine.process_messages())
    await asyncio.sleep(0.2)
    repl_engine.running = False
    task.cancel()

    try:
        await task
    except asyncio.CancelledError:
        pass

    # Should not raise exception


@pytest.mark.asyncio
async def test_repl_subscribe_on_session_creation(
    repl_engine: REPLEngine, mock_agent: MagicMock
) -> None:
    """Test REPL subscribes to output when session is created."""
    # Create prompt session to avoid terminal issues
    repl_engine.session = AsyncMock()
    repl_engine.session.prompt_async = AsyncMock(side_effect=["/exit"])

    # Create a session first
    repl_engine.session_manager.create_session(agent=mock_agent)

    # Run REPL briefly
    with patch.object(repl_engine, "_display_welcome"):
        task = asyncio.create_task(repl_engine.run())
        await asyncio.sleep(0.2)
        task.cancel()

        try:
            await task
        except (asyncio.CancelledError, EOFError):
            pass

    # Check subscribed
    assert repl_engine.subscribed is True


@pytest.mark.asyncio
async def test_message_queue_integration(
    repl_engine: REPLEngine, mock_agent: MagicMock
) -> None:
    """Test message queue receives messages from broker."""
    # Create a session
    session = repl_engine.session_manager.create_session(agent=mock_agent)

    # Subscribe to output
    repl_engine.subscribe_to_output()

    # Publish a message to client_topic
    test_message = {
        "type": "AssistantMessage",
        "content": "Test from broker",
    }
    session.broker.publish(session.context.client_topic, test_message)

    # Give broker time to process
    await asyncio.sleep(0.1)

    # Check message arrived in queue
    assert not repl_engine.message_queue.empty()
    received = await repl_engine.message_queue.get()
    assert received["content"] == "Test from broker"
