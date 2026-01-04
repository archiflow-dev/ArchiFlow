"""
Phase 3 Integration Tests for ArchiFlow Web Backend.

Tests the API endpoints that the frontend will consume.
Ensures the backend is compatible with the new frontend API client.
"""

import pytest
from httpx import AsyncClient

# We'll use the existing test fixtures from conftest.py


class TestSessionApiIntegration:
    """Test session API endpoints for frontend integration."""

    @pytest.mark.asyncio
    async def test_create_session_returns_expected_format(self, client: AsyncClient):
        """Ensure session creation returns format expected by frontend."""
        response = await client.post(
            "/api/sessions/",
            json={
                "agent_type": "coding",
                "user_prompt": "Build a login form",
            }
        )

        assert response.status_code == 201
        data = response.json()

        # Verify expected fields exist
        assert "id" in data
        assert "agent_type" in data
        assert "user_prompt" in data
        assert "status" in data
        assert "created_at" in data
        assert "updated_at" in data

        # Verify types
        assert isinstance(data["id"], str)
        assert data["agent_type"] == "coding"
        assert data["status"] in ["created", "running", "paused", "completed", "failed"]

    @pytest.mark.asyncio
    async def test_list_sessions_pagination(self, client: AsyncClient):
        """Test session list pagination format."""
        # Create a few sessions first
        for i in range(3):
            await client.post(
                "/api/sessions/",
                json={
                    "agent_type": "coding",
                    "user_prompt": f"Task {i}",
                }
            )

        response = await client.get("/api/sessions/?page=1&page_size=2")

        assert response.status_code == 200
        data = response.json()

        # Verify pagination fields
        assert "sessions" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert "has_more" in data

        assert isinstance(data["sessions"], list)
        assert data["page"] == 1
        assert data["page_size"] == 2

    @pytest.mark.asyncio
    async def test_session_lifecycle(self, client: AsyncClient):
        """Test full session lifecycle: create -> start -> pause -> resume."""
        # Create
        create_response = await client.post(
            "/api/sessions/",
            json={
                "agent_type": "coding",
                "user_prompt": "Build a component",
            }
        )
        assert create_response.status_code == 201
        session_id = create_response.json()["id"]

        # Start
        start_response = await client.post(f"/api/sessions/{session_id}/start")
        assert start_response.status_code == 200
        assert start_response.json()["status"] == "running"

        # Pause
        pause_response = await client.post(f"/api/sessions/{session_id}/pause")
        assert pause_response.status_code == 200
        assert pause_response.json()["status"] == "paused"

        # Resume
        resume_response = await client.post(f"/api/sessions/{session_id}/resume")
        assert resume_response.status_code == 200
        assert resume_response.json()["status"] == "running"

        # Delete
        delete_response = await client.delete(f"/api/sessions/{session_id}")
        assert delete_response.status_code == 204


class TestAgentApiIntegration:
    """Test agent API endpoints for frontend integration."""

    @pytest.mark.asyncio
    async def test_list_agents_format(self, client: AsyncClient):
        """Test agent list returns expected format for frontend."""
        response = await client.get("/api/agents/")

        assert response.status_code == 200
        data = response.json()

        # Verify top-level structure
        assert "agents" in data
        assert "total" in data
        assert "categories" in data

        # Verify agent structure
        if data["agents"]:
            agent = data["agents"][0]
            assert "id" in agent
            assert "name" in agent
            assert "description" in agent
            assert "category" in agent
            assert "workflow_type" in agent
            assert agent["workflow_type"] in ["phase_heavy", "chat_heavy"]

    @pytest.mark.asyncio
    async def test_get_agent_by_type(self, client: AsyncClient):
        """Test getting a specific agent type."""
        response = await client.get("/api/agents/coding")

        # Agent might exist or not depending on registry
        if response.status_code == 200:
            data = response.json()
            assert data["id"] == "coding"
            assert "capabilities" in data
        else:
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_search_agents(self, client: AsyncClient):
        """Test agent search functionality."""
        response = await client.get("/api/agents/?search=code")

        assert response.status_code == 200
        data = response.json()
        assert "agents" in data


class TestWorkflowApiIntegration:
    """Test workflow API endpoints for frontend integration."""

    @pytest.mark.asyncio
    async def test_workflow_state_format(self, client: AsyncClient):
        """Test workflow state returns expected format."""
        # Create a session first
        create_response = await client.post(
            "/api/sessions/",
            json={
                "agent_type": "comic",
                "user_prompt": "Create a comic",
            }
        )
        assert create_response.status_code == 201
        session_id = create_response.json()["id"]

        # Get workflow state
        response = await client.get(f"/api/sessions/{session_id}/workflow/")

        assert response.status_code == 200
        data = response.json()

        # Verify structure
        assert "session_id" in data
        assert "agent_type" in data
        assert "workflow_type" in data
        assert "phases" in data
        assert "total_phases" in data
        assert "completed_phases" in data
        assert "is_complete" in data

        # Verify phases structure
        if data["phases"]:
            phase = data["phases"][0]
            assert "id" in phase
            assert "name" in phase
            assert "status" in phase
            assert "order" in phase
            assert "requires_approval" in phase

    @pytest.mark.asyncio
    async def test_phase_approval_flow(self, client: AsyncClient):
        """Test phase approval workflow."""
        # Create a phase-heavy session
        create_response = await client.post(
            "/api/sessions/",
            json={
                "agent_type": "comic",
                "user_prompt": "Create a comic about AI",
            }
        )
        session_id = create_response.json()["id"]

        # Start workflow
        await client.post(f"/api/sessions/{session_id}/workflow/start")

        # Get first phase
        workflow_response = await client.get(f"/api/sessions/{session_id}/workflow/")
        phases = workflow_response.json().get("phases", [])

        if phases:
            first_phase_id = phases[0]["id"]

            # Set to awaiting approval
            await client.post(
                f"/api/sessions/{session_id}/workflow/phases/{first_phase_id}/awaiting-approval"
            )

            # Approve with feedback
            approval_response = await client.post(
                f"/api/sessions/{session_id}/workflow/phases/{first_phase_id}/approve",
                json={
                    "approved": True,
                    "feedback": "Looks good!"
                }
            )

            assert approval_response.status_code == 200
            data = approval_response.json()
            assert "phase_id" in data
            assert "status" in data
            assert "message" in data


class TestArtifactApiIntegration:
    """Test artifact API endpoints for frontend integration."""

    @pytest.mark.asyncio
    async def test_list_artifacts_format(self, client: AsyncClient):
        """Test artifact list returns expected format."""
        # Create a session
        create_response = await client.post(
            "/api/sessions/",
            json={
                "agent_type": "coding",
                "user_prompt": "Build something",
            }
        )
        session_id = create_response.json()["id"]

        # List artifacts
        response = await client.get(f"/api/sessions/{session_id}/artifacts/")

        assert response.status_code == 200
        data = response.json()

        # Verify structure
        assert "artifacts" in data
        assert "path" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_create_and_get_artifact(self, client: AsyncClient):
        """Test creating and retrieving an artifact."""
        # Create a session
        create_response = await client.post(
            "/api/sessions/",
            json={
                "agent_type": "coding",
                "user_prompt": "Build something",
            }
        )
        session_id = create_response.json()["id"]

        # Create an artifact
        artifact_response = await client.post(
            f"/api/sessions/{session_id}/artifacts/",
            json={
                "path": "test.md",
                "content": "# Test\n\nThis is a test file.",
            }
        )

        assert artifact_response.status_code == 201
        artifact = artifact_response.json()
        assert artifact["path"] == "test.md"
        assert artifact["is_directory"] is False

        # Get the artifact content
        get_response = await client.get(f"/api/sessions/{session_id}/artifacts/test.md")

        assert get_response.status_code == 200
        content = get_response.json()
        assert content["content"] == "# Test\n\nThis is a test file."
        assert content["is_binary"] is False


class TestMessageApiIntegration:
    """Test message API endpoints for frontend integration."""

    @pytest.mark.asyncio
    async def test_list_messages_format(self, client: AsyncClient):
        """Test message list returns expected format."""
        # Create a session
        create_response = await client.post(
            "/api/sessions/",
            json={
                "agent_type": "coding",
                "user_prompt": "Build something",
            }
        )
        session_id = create_response.json()["id"]

        # List messages
        response = await client.get(f"/api/sessions/{session_id}/messages/")

        assert response.status_code == 200
        data = response.json()

        # Verify structure
        assert "messages" in data
        assert "total" in data
        assert "session_id" in data

    @pytest.mark.asyncio
    async def test_send_message(self, client: AsyncClient):
        """Test sending a message to a session."""
        # Create a session
        create_response = await client.post(
            "/api/sessions/",
            json={
                "agent_type": "coding",
                "user_prompt": "Build something",
            }
        )
        session_id = create_response.json()["id"]

        # Send a message
        response = await client.post(
            f"/api/sessions/{session_id}/messages/",
            json={
                "role": "user",
                "content": "Can you help me with this?",
            }
        )

        assert response.status_code == 201
        data = response.json()

        # Verify structure
        assert "id" in data
        assert "session_id" in data
        assert "role" in data
        assert "content" in data
        assert "sequence" in data
        assert "created_at" in data

        assert data["role"] == "user"
        assert data["content"] == "Can you help me with this?"


class TestHealthEndpoint:
    """Test health check endpoint."""

    @pytest.mark.asyncio
    async def test_health_check(self, client: AsyncClient):
        """Test health endpoint for frontend API health check."""
        response = await client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["ok", "healthy"]
