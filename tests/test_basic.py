"""
Basic tests to verify setup.
"""

import asyncio

import pytest


def test_basic_import() -> None:
    """Test that the package can be imported."""
    import agent_cli

    assert agent_cli.__version__ == "0.1.0"


def test_pytest_works() -> None:
    """Test that pytest is working."""
    assert True


@pytest.mark.asyncio
async def test_async_works() -> None:
    """Test that async tests work."""
    await asyncio.sleep(0.001)
    assert True
