"""
Tests for agent API endpoints.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_agents(client: AsyncClient):
    """Test listing all available agents."""
    response = await client.get("/api/agents/")

    assert response.status_code == 200
    data = response.json()

    assert "agents" in data
    assert "total" in data
    assert "categories" in data
    assert len(data["agents"]) > 0
    assert data["total"] == len(data["agents"])


@pytest.mark.asyncio
async def test_list_agents_structure(client: AsyncClient):
    """Test that agent list has correct structure."""
    response = await client.get("/api/agents/")
    data = response.json()

    for agent in data["agents"]:
        # Check required fields (new API structure)
        assert "id" in agent  # aliased from "type"
        assert "name" in agent
        assert "description" in agent
        assert "category" in agent
        assert "workflow_type" in agent
        assert "capabilities" in agent
        assert "icon" in agent
        assert "color" in agent

        # Check workflow_type is valid
        assert agent["workflow_type"] in ["phase_heavy", "chat_heavy"]


@pytest.mark.asyncio
async def test_get_agent_comic(client: AsyncClient):
    """Test getting the comic agent."""
    response = await client.get("/api/agents/comic")

    assert response.status_code == 200
    data = response.json()

    assert data["id"] == "comic"
    assert data["name"] == "Comic Creator"
    assert data["workflow_type"] == "phase_heavy"
    assert len(data["capabilities"]) > 0


@pytest.mark.asyncio
async def test_get_agent_ppt(client: AsyncClient):
    """Test getting the PPT agent."""
    response = await client.get("/api/agents/ppt")

    assert response.status_code == 200
    data = response.json()

    assert data["id"] == "ppt"
    assert data["name"] == "Presentation Designer"
    assert data["workflow_type"] == "phase_heavy"


@pytest.mark.asyncio
async def test_get_agent_coding(client: AsyncClient):
    """Test getting the coding agent."""
    response = await client.get("/api/agents/coding")

    assert response.status_code == 200
    data = response.json()

    assert data["id"] == "coding"
    assert data["name"] == "Coding Assistant"
    assert data["workflow_type"] == "chat_heavy"


@pytest.mark.asyncio
async def test_get_agent_not_found(client: AsyncClient):
    """Test getting a non-existent agent."""
    response = await client.get("/api/agents/nonexistent")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_agent_workflow_endpoint(client: AsyncClient):
    """Test that agent workflow endpoint returns phases."""
    response = await client.get("/api/agents/comic/workflow")

    assert response.status_code == 200
    data = response.json()

    assert "agent_type" in data
    assert "workflow_type" in data
    assert "phases" in data
    assert "total_phases" in data

    for phase in data["phases"]:
        assert "id" in phase
        assert "name" in phase
        assert "requires_approval" in phase
        assert "artifacts" in phase
        assert isinstance(phase["requires_approval"], bool)
        assert isinstance(phase["artifacts"], list)


@pytest.mark.asyncio
async def test_comic_agent_workflow_phases(client: AsyncClient):
    """Test that comic agent workflow has expected phases."""
    response = await client.get("/api/agents/comic/workflow")
    data = response.json()

    phase_ids = [p["id"] for p in data["phases"]]

    # Comic agent should have these phases
    expected_phases = [
        "script_generation",
        "visual_specification",
        "character_references",
        "panel_generation",
        "export"
    ]

    for expected in expected_phases:
        assert expected in phase_ids, f"Missing phase: {expected}"


@pytest.mark.asyncio
async def test_agent_categories(client: AsyncClient):
    """Test that agents have valid categories."""
    response = await client.get("/api/agents/")
    data = response.json()

    valid_categories = ["creative", "development", "research", "general"]

    for agent in data["agents"]:
        assert agent["category"] in valid_categories, \
            f"Invalid category: {agent['category']}"


@pytest.mark.asyncio
async def test_agent_capabilities(client: AsyncClient):
    """Test that agents have capabilities."""
    response = await client.get("/api/agents/")
    data = response.json()

    for agent in data["agents"]:
        assert isinstance(agent["capabilities"], list)
        # All agents should have at least one capability
        assert len(agent["capabilities"]) > 0

        # Check capability structure
        for cap in agent["capabilities"]:
            assert "name" in cap
            assert "description" in cap


@pytest.mark.asyncio
async def test_agent_categories_endpoint(client: AsyncClient):
    """Test the categories endpoint."""
    response = await client.get("/api/agents/categories")

    assert response.status_code == 200
    data = response.json()

    assert "categories" in data
    for cat in data["categories"]:
        assert "id" in cat
        assert "name" in cat
        assert "count" in cat


@pytest.mark.asyncio
async def test_list_agents_filter_by_category(client: AsyncClient):
    """Test filtering agents by category."""
    response = await client.get("/api/agents/?category=creative")

    assert response.status_code == 200
    data = response.json()

    # All returned agents should be in creative category
    for agent in data["agents"]:
        assert agent["category"] == "creative"


@pytest.mark.asyncio
async def test_list_agents_search(client: AsyncClient):
    """Test searching agents."""
    response = await client.get("/api/agents/?search=comic")

    assert response.status_code == 200
    data = response.json()

    assert len(data["agents"]) >= 1
    # Comic agent should be in results
    types = [a["id"] for a in data["agents"]]
    assert "comic" in types
