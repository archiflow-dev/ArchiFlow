"""
Tests for WebSocket connection manager.
"""

import pytest
import asyncio

from src.web_backend.websocket.manager import ConnectionManager, ClientInfo


@pytest.fixture
def manager() -> ConnectionManager:
    """Create a fresh connection manager for each test."""
    return ConnectionManager()


@pytest.mark.asyncio
async def test_connect(manager: ConnectionManager):
    """Test client connection."""
    await manager.connect("client1", "user1")

    assert manager.connected_clients == 1
    client = manager.get_client_info("client1")
    assert client is not None
    assert client.sid == "client1"
    assert client.user_id == "user1"


@pytest.mark.asyncio
async def test_connect_without_user_id(manager: ConnectionManager):
    """Test client connection without user ID."""
    await manager.connect("client1")

    client = manager.get_client_info("client1")
    assert client is not None
    assert client.user_id is None


@pytest.mark.asyncio
async def test_disconnect(manager: ConnectionManager):
    """Test client disconnection."""
    await manager.connect("client1", "user1")
    await manager.disconnect("client1")

    assert manager.connected_clients == 0
    assert manager.get_client_info("client1") is None


@pytest.mark.asyncio
async def test_disconnect_unknown_client(manager: ConnectionManager):
    """Test disconnecting unknown client doesn't raise error."""
    await manager.disconnect("unknown_client")  # Should not raise


@pytest.mark.asyncio
async def test_subscribe_to_session(manager: ConnectionManager):
    """Test subscribing to a session."""
    await manager.connect("client1", "user1")
    success = await manager.subscribe_to_session("client1", "session1")

    assert success is True
    assert manager.active_sessions == 1

    subscribers = manager.get_session_subscribers("session1")
    assert "client1" in subscribers

    client = manager.get_client_info("client1")
    assert "session1" in client.subscribed_sessions


@pytest.mark.asyncio
async def test_subscribe_unknown_client(manager: ConnectionManager):
    """Test subscribing with unknown client fails."""
    success = await manager.subscribe_to_session("unknown", "session1")
    assert success is False


@pytest.mark.asyncio
async def test_unsubscribe_from_session(manager: ConnectionManager):
    """Test unsubscribing from a session."""
    await manager.connect("client1", "user1")
    await manager.subscribe_to_session("client1", "session1")
    await manager.unsubscribe_from_session("client1", "session1")

    subscribers = manager.get_session_subscribers("session1")
    assert "client1" not in subscribers

    client = manager.get_client_info("client1")
    assert "session1" not in client.subscribed_sessions


@pytest.mark.asyncio
async def test_unsubscribe_unknown_client(manager: ConnectionManager):
    """Test unsubscribing unknown client."""
    success = await manager.unsubscribe_from_session("unknown", "session1")
    assert success is False


@pytest.mark.asyncio
async def test_multiple_subscribers(manager: ConnectionManager):
    """Test multiple clients subscribing to same session."""
    await manager.connect("client1", "user1")
    await manager.connect("client2", "user2")

    await manager.subscribe_to_session("client1", "session1")
    await manager.subscribe_to_session("client2", "session1")

    subscribers = manager.get_session_subscribers("session1")
    assert len(subscribers) == 2
    assert "client1" in subscribers
    assert "client2" in subscribers


@pytest.mark.asyncio
async def test_client_multiple_sessions(manager: ConnectionManager):
    """Test client subscribing to multiple sessions."""
    await manager.connect("client1", "user1")

    await manager.subscribe_to_session("client1", "session1")
    await manager.subscribe_to_session("client1", "session2")
    await manager.subscribe_to_session("client1", "session3")

    client = manager.get_client_info("client1")
    assert len(client.subscribed_sessions) == 3
    assert manager.active_sessions == 3


@pytest.mark.asyncio
async def test_disconnect_cleans_subscriptions(manager: ConnectionManager):
    """Test that disconnecting cleans up subscriptions."""
    await manager.connect("client1", "user1")
    await manager.subscribe_to_session("client1", "session1")
    await manager.subscribe_to_session("client1", "session2")

    await manager.disconnect("client1")

    # All sessions should have no subscribers
    assert len(manager.get_session_subscribers("session1")) == 0
    assert len(manager.get_session_subscribers("session2")) == 0
    assert manager.active_sessions == 0


@pytest.mark.asyncio
async def test_get_session_subscribers_empty(manager: ConnectionManager):
    """Test getting subscribers for session with none."""
    subscribers = manager.get_session_subscribers("nonexistent")
    assert subscribers == set()


@pytest.mark.asyncio
async def test_connected_clients_count(manager: ConnectionManager):
    """Test connected clients counter."""
    assert manager.connected_clients == 0

    await manager.connect("client1")
    assert manager.connected_clients == 1

    await manager.connect("client2")
    assert manager.connected_clients == 2

    await manager.disconnect("client1")
    assert manager.connected_clients == 1


@pytest.mark.asyncio
async def test_active_sessions_count(manager: ConnectionManager):
    """Test active sessions counter."""
    await manager.connect("client1")
    await manager.connect("client2")

    assert manager.active_sessions == 0

    await manager.subscribe_to_session("client1", "session1")
    assert manager.active_sessions == 1

    await manager.subscribe_to_session("client2", "session2")
    assert manager.active_sessions == 2

    await manager.unsubscribe_from_session("client1", "session1")
    assert manager.active_sessions == 1


@pytest.mark.asyncio
async def test_concurrent_operations(manager: ConnectionManager):
    """Test concurrent connect/disconnect operations."""
    async def connect_and_subscribe(client_id: str, session_id: str):
        await manager.connect(client_id)
        await manager.subscribe_to_session(client_id, session_id)
        await asyncio.sleep(0.01)  # Small delay
        await manager.disconnect(client_id)

    # Run multiple concurrent operations
    tasks = [
        connect_and_subscribe(f"client{i}", "session1")
        for i in range(10)
    ]

    await asyncio.gather(*tasks)

    # All should be cleaned up
    assert manager.connected_clients == 0


@pytest.mark.asyncio
async def test_client_info_connected_at(manager: ConnectionManager):
    """Test that connected_at is set on connection."""
    import time
    before = time.time()

    await manager.connect("client1")

    after = time.time()
    client = manager.get_client_info("client1")

    assert before <= client.connected_at <= after
