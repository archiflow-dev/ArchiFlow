"""
Tests for message API endpoints.
"""

import pytest
from httpx import AsyncClient


@pytest.fixture
async def session_id(client: AsyncClient) -> str:
    """Create a session and return its ID."""
    response = await client.post("/api/sessions/", json={
        "agent_type": "comic",
        "user_prompt": "Test prompt",
    })
    return response.json()["id"]


@pytest.mark.asyncio
async def test_send_message(client: AsyncClient, session_id: str, sample_message_data: dict):
    """Test sending a message to a session."""
    response = await client.post(
        f"/api/sessions/{session_id}/messages/",
        json=sample_message_data
    )

    assert response.status_code == 201
    data = response.json()

    assert "id" in data
    assert data["session_id"] == session_id
    assert data["content"] == sample_message_data["content"]
    assert data["role"] == sample_message_data["role"]
    assert data["sequence"] == 1  # First message


@pytest.mark.asyncio
async def test_send_message_sequence(client: AsyncClient, session_id: str):
    """Test that message sequence numbers increment."""
    # Send multiple messages
    for i in range(3):
        response = await client.post(
            f"/api/sessions/{session_id}/messages/",
            json={"content": f"Message {i}", "role": "user"}
        )
        data = response.json()
        assert data["sequence"] == i + 1


@pytest.mark.asyncio
async def test_send_message_default_role(client: AsyncClient, session_id: str):
    """Test that default role is user."""
    response = await client.post(
        f"/api/sessions/{session_id}/messages/",
        json={"content": "Test message"}  # No role specified
    )

    assert response.status_code == 201
    data = response.json()
    assert data["role"] == "user"


@pytest.mark.asyncio
async def test_send_message_validation(client: AsyncClient, session_id: str):
    """Test message validation."""
    # Empty content should fail
    response = await client.post(
        f"/api/sessions/{session_id}/messages/",
        json={"content": "", "role": "user"}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_messages_empty(client: AsyncClient, session_id: str):
    """Test listing messages when none exist."""
    response = await client.get(f"/api/sessions/{session_id}/messages/")

    assert response.status_code == 200
    data = response.json()
    assert data["messages"] == []
    assert data["total"] == 0
    assert data["session_id"] == session_id


@pytest.mark.asyncio
async def test_list_messages(client: AsyncClient, session_id: str):
    """Test listing messages after sending some."""
    # Send messages
    await client.post(
        f"/api/sessions/{session_id}/messages/",
        json={"content": "First message", "role": "user"}
    )
    await client.post(
        f"/api/sessions/{session_id}/messages/",
        json={"content": "Second message", "role": "user"}
    )

    response = await client.get(f"/api/sessions/{session_id}/messages/")

    assert response.status_code == 200
    data = response.json()
    assert len(data["messages"]) == 2
    assert data["total"] == 2

    # Check ordering (should be by sequence)
    assert data["messages"][0]["sequence"] < data["messages"][1]["sequence"]


@pytest.mark.asyncio
async def test_list_messages_pagination(client: AsyncClient, session_id: str):
    """Test message listing pagination."""
    # Send multiple messages
    for i in range(5):
        await client.post(
            f"/api/sessions/{session_id}/messages/",
            json={"content": f"Message {i}", "role": "user"}
        )

    # Get with limit
    response = await client.get(
        f"/api/sessions/{session_id}/messages/",
        params={"limit": 2}
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["messages"]) == 2
    assert data["total"] == 5


@pytest.mark.asyncio
async def test_list_messages_offset(client: AsyncClient, session_id: str):
    """Test message listing with offset."""
    # Send multiple messages
    for i in range(5):
        await client.post(
            f"/api/sessions/{session_id}/messages/",
            json={"content": f"Message {i}", "role": "user"}
        )

    # Get with offset
    response = await client.get(
        f"/api/sessions/{session_id}/messages/",
        params={"offset": 2, "limit": 10}
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["messages"]) == 3
    # First message should be sequence 3 (offset skips 1 and 2)
    assert data["messages"][0]["sequence"] == 3


@pytest.mark.asyncio
async def test_get_message(client: AsyncClient, session_id: str):
    """Test getting a specific message."""
    # Create a message
    create_response = await client.post(
        f"/api/sessions/{session_id}/messages/",
        json={"content": "Test message", "role": "user"}
    )
    message_id = create_response.json()["id"]

    # Get the message
    response = await client.get(f"/api/sessions/{session_id}/messages/{message_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == message_id
    assert data["content"] == "Test message"


@pytest.mark.asyncio
async def test_get_message_not_found(client: AsyncClient, session_id: str):
    """Test getting a non-existent message."""
    response = await client.get(f"/api/sessions/{session_id}/messages/nonexistent_id")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_message_roles(client: AsyncClient, session_id: str):
    """Test different message roles."""
    roles = ["user", "assistant", "system", "tool"]

    for role in roles:
        response = await client.post(
            f"/api/sessions/{session_id}/messages/",
            json={"content": f"Message with role {role}", "role": role}
        )
        assert response.status_code == 201
        assert response.json()["role"] == role


@pytest.mark.asyncio
async def test_message_response_fields(client: AsyncClient, session_id: str):
    """Test that message response has all required fields."""
    response = await client.post(
        f"/api/sessions/{session_id}/messages/",
        json={"content": "Test", "role": "user"}
    )

    data = response.json()

    required_fields = [
        "id", "session_id", "role", "content",
        "sequence", "created_at"
    ]

    for field in required_fields:
        assert field in data, f"Missing field: {field}"
