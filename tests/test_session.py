"""
Tests for session management.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from agent_cli.session.manager import CLISession, SessionManager


@pytest.fixture
def mock_agent() -> MagicMock:
    """Create a mock agent."""
    agent = MagicMock()
    agent.session_id = "test_session"
    agent.tools = MagicMock()
    return agent


@pytest.fixture
def session_manager() -> SessionManager:
    """Create a session manager."""
    return SessionManager()


def test_session_manager_init() -> None:
    """Test session manager initialization."""
    manager = SessionManager()
    assert manager.sessions == {}
    assert manager.active_session_id is None


def test_create_session(session_manager: SessionManager, mock_agent: MagicMock) -> None:
    """Test creating a session."""
    session = session_manager.create_session(agent=mock_agent)

    assert isinstance(session, CLISession)
    assert session.session_id == "test_session"
    assert session.agent == mock_agent
    assert session.broker is not None
    assert session.context is not None
    assert session.controller is not None
    assert session.executor is not None
    assert session.active is True


def test_create_session_auto_id(
    session_manager: SessionManager, mock_agent: MagicMock
) -> None:
    """Test creating session with auto-generated ID."""
    mock_agent.session_id = None
    session = session_manager.create_session(agent=mock_agent, session_id="custom_id")

    assert session.session_id == "custom_id"


def test_get_session(session_manager: SessionManager, mock_agent: MagicMock) -> None:
    """Test getting a session by ID."""
    session = session_manager.create_session(agent=mock_agent)

    retrieved = session_manager.get_session("test_session")
    assert retrieved == session


def test_get_session_not_found(session_manager: SessionManager) -> None:
    """Test getting non-existent session."""
    result = session_manager.get_session("nonexistent")
    assert result is None


def test_get_active_session(
    session_manager: SessionManager, mock_agent: MagicMock
) -> None:
    """Test getting the active session."""
    session = session_manager.create_session(agent=mock_agent)

    active = session_manager.get_active_session()
    assert active == session


def test_get_active_session_none(session_manager: SessionManager) -> None:
    """Test getting active session when none exists."""
    result = session_manager.get_active_session()
    assert result is None


def test_list_sessions(session_manager: SessionManager, mock_agent: MagicMock) -> None:
    """Test listing all sessions."""
    session1 = session_manager.create_session(agent=mock_agent, session_id="session1")

    mock_agent2 = MagicMock()
    mock_agent2.tools = MagicMock()
    session2 = session_manager.create_session(agent=mock_agent2, session_id="session2")

    sessions = session_manager.list_sessions()
    assert len(sessions) == 2
    assert session1 in sessions
    assert session2 in sessions


def test_send_message(session_manager: SessionManager, mock_agent: MagicMock) -> None:
    """Test sending a message to agent."""
    session = session_manager.create_session(agent=mock_agent)

    result = session_manager.send_message("Hello, agent!")
    assert result is True


def test_send_message_no_session(session_manager: SessionManager) -> None:
    """Test sending message with no active session."""
    result = session_manager.send_message("Hello")
    assert result is False


def test_close_session(session_manager: SessionManager, mock_agent: MagicMock) -> None:
    """Test closing a session."""
    session = session_manager.create_session(agent=mock_agent)

    result = session_manager.close_session("test_session")
    assert result is True
    assert session_manager.get_session("test_session") is None
    assert session_manager.active_session_id is None


def test_close_session_not_found(session_manager: SessionManager) -> None:
    """Test closing non-existent session."""
    result = session_manager.close_session("nonexistent")
    assert result is False


def test_close_all_sessions(
    session_manager: SessionManager, mock_agent: MagicMock
) -> None:
    """Test closing all sessions."""
    session_manager.create_session(agent=mock_agent, session_id="session1")

    mock_agent2 = MagicMock()
    mock_agent2.tools = MagicMock()
    session_manager.create_session(agent=mock_agent2, session_id="session2")

    session_manager.close_all_sessions()
    assert len(session_manager.sessions) == 0
    assert session_manager.active_session_id is None


def test_topic_context_created(
    session_manager: SessionManager, mock_agent: MagicMock
) -> None:
    """Test that topic context is created correctly."""
    session = session_manager.create_session(agent=mock_agent, session_id="test_123")

    # Check topic names
    assert "test_123" in session.context.agent_topic
    assert "test_123" in session.context.client_topic
    assert "test_123" in session.context.runtime_topic
