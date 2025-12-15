"""
Pytest configuration and fixtures for all tests.

This conftest.py registers all tools globally before running any tests.
"""

import pytest
from agent_framework.tools import all_tools


@pytest.fixture(scope="session", autouse=True)
def register_all_tools():
    """
    Register all tools before running tests.

    This is a session-scoped fixture that runs automatically for all tests.
    It ensures that the global tool registry is populated with all available
    tools before any agent tests run.
    """
    # Register all tools in the global singleton registry
    all_tools.register_all_tools()

    yield

    # Cleanup: Clear the registry after tests
    # (Tools are singletons, so we don't actually need to clean up)
