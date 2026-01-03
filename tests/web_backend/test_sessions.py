"""
Tests for session API endpoints.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_session(client: AsyncClient, sample_session_data: dict):
    """Test creating a new session."""
    response = await client.post("/api/sessions/", json=sample_session_data)

    assert response.status_code == 201
    data = response.json()

    assert "id" in data
    assert data["agent_type"] == sample_session_data["agent_type"]
    assert data["user_prompt"] == sample_session_data["user_prompt"]
    assert data["status"] == "created"
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_create_session_minimal(client: AsyncClient):
    """Test creating a session with minimal data."""
    minimal_data = {
        "agent_type": "coding",
        "user_prompt": "Fix the bug",
    }

    response = await client.post("/api/sessions/", json=minimal_data)

    assert response.status_code == 201
    data = response.json()
    assert data["agent_type"] == "coding"
    assert data["project_directory"] is None


@pytest.mark.asyncio
async def test_create_session_validation_error(client: AsyncClient):
    """Test session creation with invalid data."""
    invalid_data = {
        "agent_type": "",  # Empty string should fail
        "user_prompt": "Test",
    }

    response = await client.post("/api/sessions/", json=invalid_data)
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_session_missing_required_field(client: AsyncClient):
    """Test session creation with missing required field."""
    incomplete_data = {
        "agent_type": "comic",
        # Missing user_prompt
    }

    response = await client.post("/api/sessions/", json=incomplete_data)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_session(client: AsyncClient, sample_session_data: dict):
    """Test getting a specific session."""
    # Create a session first
    create_response = await client.post("/api/sessions/", json=sample_session_data)
    session_id = create_response.json()["id"]

    # Get the session
    response = await client.get(f"/api/sessions/{session_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == session_id
    assert data["agent_type"] == sample_session_data["agent_type"]


@pytest.mark.asyncio
async def test_get_session_not_found(client: AsyncClient):
    """Test getting a non-existent session."""
    response = await client.get("/api/sessions/nonexistent_session_id")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_list_sessions_empty(client: AsyncClient):
    """Test listing sessions when none exist."""
    response = await client.get("/api/sessions/")

    assert response.status_code == 200
    data = response.json()
    assert data["sessions"] == []
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["has_more"] is False


@pytest.mark.asyncio
async def test_list_sessions(client: AsyncClient, sample_session_data: dict):
    """Test listing sessions after creating some."""
    # Create multiple sessions
    await client.post("/api/sessions/", json=sample_session_data)
    await client.post("/api/sessions/", json={
        "agent_type": "ppt",
        "user_prompt": "Create a presentation",
    })

    response = await client.get("/api/sessions/")

    assert response.status_code == 200
    data = response.json()
    assert len(data["sessions"]) == 2
    assert data["total"] == 2


@pytest.mark.asyncio
async def test_list_sessions_filter_by_agent_type(client: AsyncClient, sample_session_data: dict):
    """Test filtering sessions by agent type."""
    # Create sessions with different agent types
    await client.post("/api/sessions/", json=sample_session_data)  # comic
    await client.post("/api/sessions/", json={
        "agent_type": "ppt",
        "user_prompt": "Create a presentation",
    })

    # Filter by comic
    response = await client.get("/api/sessions/", params={"agent_type": "comic"})

    assert response.status_code == 200
    data = response.json()
    assert len(data["sessions"]) == 1
    assert data["sessions"][0]["agent_type"] == "comic"


@pytest.mark.asyncio
async def test_list_sessions_pagination(client: AsyncClient):
    """Test session listing pagination."""
    # Create multiple sessions
    for i in range(5):
        await client.post("/api/sessions/", json={
            "agent_type": "comic",
            "user_prompt": f"Test prompt {i}",
        })

    # Get first page with page_size=2
    response = await client.get("/api/sessions/", params={"page": 1, "page_size": 2})

    assert response.status_code == 200
    data = response.json()
    assert len(data["sessions"]) == 2
    assert data["total"] == 5
    assert data["has_more"] is True

    # Get second page
    response = await client.get("/api/sessions/", params={"page": 2, "page_size": 2})
    data = response.json()
    assert len(data["sessions"]) == 2
    assert data["has_more"] is True

    # Get last page
    response = await client.get("/api/sessions/", params={"page": 3, "page_size": 2})
    data = response.json()
    assert len(data["sessions"]) == 1
    assert data["has_more"] is False


@pytest.mark.asyncio
async def test_update_session_status(client: AsyncClient, sample_session_data: dict):
    """Test updating a session's status."""
    # Create a session
    create_response = await client.post("/api/sessions/", json=sample_session_data)
    session_id = create_response.json()["id"]

    # Update status to paused
    response = await client.patch(
        f"/api/sessions/{session_id}",
        json={"status": "paused"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "paused"


@pytest.mark.asyncio
async def test_update_session_not_found(client: AsyncClient):
    """Test updating a non-existent session."""
    response = await client.patch(
        "/api/sessions/nonexistent_id",
        json={"status": "paused"}
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_session(client: AsyncClient, sample_session_data: dict):
    """Test deleting a session."""
    # Create a session
    create_response = await client.post("/api/sessions/", json=sample_session_data)
    session_id = create_response.json()["id"]

    # Delete the session
    response = await client.delete(f"/api/sessions/{session_id}")
    assert response.status_code == 204

    # Verify it's gone
    get_response = await client.get(f"/api/sessions/{session_id}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_session_not_found(client: AsyncClient):
    """Test deleting a non-existent session."""
    response = await client.delete("/api/sessions/nonexistent_id")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_start_session(client: AsyncClient, sample_session_data: dict):
    """Test starting a session."""
    # Create a session
    create_response = await client.post("/api/sessions/", json=sample_session_data)
    session_id = create_response.json()["id"]

    # Start the session
    response = await client.post(f"/api/sessions/{session_id}/start")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "running"


@pytest.mark.asyncio
async def test_pause_session(client: AsyncClient, sample_session_data: dict):
    """Test pausing a session."""
    # Create and start a session
    create_response = await client.post("/api/sessions/", json=sample_session_data)
    session_id = create_response.json()["id"]
    await client.post(f"/api/sessions/{session_id}/start")

    # Pause the session
    response = await client.post(f"/api/sessions/{session_id}/pause")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "paused"


@pytest.mark.asyncio
async def test_resume_session(client: AsyncClient, sample_session_data: dict):
    """Test resuming a paused session."""
    # Create, start, and pause a session
    create_response = await client.post("/api/sessions/", json=sample_session_data)
    session_id = create_response.json()["id"]
    await client.post(f"/api/sessions/{session_id}/start")
    await client.post(f"/api/sessions/{session_id}/pause")

    # Resume the session
    response = await client.post(f"/api/sessions/{session_id}/resume")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "running"
