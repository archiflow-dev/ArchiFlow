"""
Tests for health check endpoint.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Test health check endpoint returns healthy status."""
    response = await client.get("/api/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert data["version"] == "3.1.0"
    assert "app_name" in data


@pytest.mark.asyncio
async def test_health_check_response_format(client: AsyncClient):
    """Test health check response has correct format."""
    response = await client.get("/api/health")

    assert response.status_code == 200
    data = response.json()

    # Check all required fields
    required_fields = ["status", "version", "app_name"]
    for field in required_fields:
        assert field in data, f"Missing field: {field}"

    # Check types
    assert isinstance(data["status"], str)
    assert isinstance(data["version"], str)
    assert isinstance(data["app_name"], str)
