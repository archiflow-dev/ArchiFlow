"""
Tests for database models.
"""

import pytest
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from src.web_backend.models.session import Session, SessionStatus, generate_session_id
from src.web_backend.models.message import Message, MessageRole, generate_message_id


class TestSessionModel:
    """Tests for Session model."""

    def test_generate_session_id(self):
        """Test session ID generation."""
        id1 = generate_session_id()
        id2 = generate_session_id()

        assert id1.startswith("session_")
        assert id2.startswith("session_")
        assert id1 != id2  # Should be unique
        assert len(id1) == len("session_") + 12  # 12 hex chars

    def test_session_status_values(self):
        """Test session status enum values."""
        assert SessionStatus.CREATED.value == "created"
        assert SessionStatus.RUNNING.value == "running"
        assert SessionStatus.PAUSED.value == "paused"
        assert SessionStatus.AWAITING_INPUT.value == "awaiting_input"
        assert SessionStatus.COMPLETED.value == "completed"
        assert SessionStatus.FAILED.value == "failed"

    @pytest.mark.asyncio
    async def test_session_creation(self, db_session: AsyncSession):
        """Test creating a session in the database."""
        session = Session(
            agent_type="comic",
            user_prompt="Test prompt",
            status=SessionStatus.CREATED,
        )

        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)

        assert session.id is not None
        assert session.id.startswith("session_")
        assert session.agent_type == "comic"
        assert session.user_prompt == "Test prompt"
        assert session.status == SessionStatus.CREATED
        assert session.created_at is not None
        assert session.updated_at is not None

    @pytest.mark.asyncio
    async def test_session_to_dict(self, db_session: AsyncSession):
        """Test session to_dict method."""
        session = Session(
            agent_type="ppt",
            user_prompt="Create presentation",
            project_directory="/path/to/project",
        )

        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)

        data = session.to_dict()

        assert "id" in data
        assert data["agent_type"] == "ppt"
        assert data["user_prompt"] == "Create presentation"
        assert data["project_directory"] == "/path/to/project"
        assert data["status"] == "created"
        assert "created_at" in data
        assert "updated_at" in data

    @pytest.mark.asyncio
    async def test_session_repr(self, db_session: AsyncSession):
        """Test session __repr__ method."""
        session = Session(
            agent_type="comic",
            user_prompt="Test",
        )

        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)

        repr_str = repr(session)

        assert "Session" in repr_str
        assert session.id in repr_str
        assert "comic" in repr_str

    @pytest.mark.asyncio
    async def test_session_workflow_state(self, db_session: AsyncSession):
        """Test session with workflow state."""
        workflow_state = {
            "current_phase": "script_generation",
            "completed_phases": [],
        }

        session = Session(
            agent_type="comic",
            user_prompt="Test",
            workflow_state=workflow_state,
        )

        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)

        assert session.workflow_state == workflow_state


class TestMessageModel:
    """Tests for Message model."""

    def test_generate_message_id(self):
        """Test message ID generation."""
        id1 = generate_message_id()
        id2 = generate_message_id()

        assert id1.startswith("msg_")
        assert id2.startswith("msg_")
        assert id1 != id2  # Should be unique

    def test_message_role_values(self):
        """Test message role enum values."""
        assert MessageRole.USER.value == "user"
        assert MessageRole.ASSISTANT.value == "assistant"
        assert MessageRole.SYSTEM.value == "system"
        assert MessageRole.TOOL.value == "tool"

    @pytest.mark.asyncio
    async def test_message_creation(self, db_session: AsyncSession):
        """Test creating a message in the database."""
        # First create a session
        session = Session(
            agent_type="comic",
            user_prompt="Test",
        )
        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)

        # Create message
        message = Message(
            session_id=session.id,
            role=MessageRole.USER,
            content="Hello, agent!",
            sequence=1,
        )

        db_session.add(message)
        await db_session.commit()
        await db_session.refresh(message)

        assert message.id is not None
        assert message.id.startswith("msg_")
        assert message.session_id == session.id
        assert message.role == MessageRole.USER
        assert message.content == "Hello, agent!"
        assert message.sequence == 1
        assert message.created_at is not None

    @pytest.mark.asyncio
    async def test_message_to_dict(self, db_session: AsyncSession):
        """Test message to_dict method."""
        # Create session first
        session = Session(
            agent_type="comic",
            user_prompt="Test",
        )
        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)

        # Create message
        message = Message(
            session_id=session.id,
            role=MessageRole.ASSISTANT,
            content="I'll help you create a comic.",
            sequence=2,
        )

        db_session.add(message)
        await db_session.commit()
        await db_session.refresh(message)

        data = message.to_dict()

        assert "id" in data
        assert data["session_id"] == session.id
        assert data["role"] == "assistant"
        assert data["content"] == "I'll help you create a comic."
        assert data["sequence"] == 2
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_message_repr(self, db_session: AsyncSession):
        """Test message __repr__ method."""
        # Create session
        session = Session(
            agent_type="comic",
            user_prompt="Test",
        )
        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)

        # Create message
        message = Message(
            session_id=session.id,
            role=MessageRole.USER,
            content="This is a test message with some content",
            sequence=1,
        )

        db_session.add(message)
        await db_session.commit()
        await db_session.refresh(message)

        repr_str = repr(message)

        assert "Message" in repr_str
        assert "USER" in repr_str  # Enum shows as MessageRole.USER

    @pytest.mark.asyncio
    async def test_message_tool_fields(self, db_session: AsyncSession):
        """Test message with tool-related fields."""
        # Create session
        session = Session(
            agent_type="coding",
            user_prompt="Test",
        )
        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)

        # Create tool message
        message = Message(
            session_id=session.id,
            role=MessageRole.TOOL,
            content='{"result": "success"}',
            sequence=1,
            tool_name="write_file",
            tool_call_id="call_123",
        )

        db_session.add(message)
        await db_session.commit()
        await db_session.refresh(message)

        assert message.tool_name == "write_file"
        assert message.tool_call_id == "call_123"

    @pytest.mark.asyncio
    async def test_session_message_relationship(self, db_session: AsyncSession):
        """Test session-message relationship."""
        # Create session
        session = Session(
            agent_type="comic",
            user_prompt="Test",
        )
        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)

        # Create multiple messages
        for i in range(3):
            message = Message(
                session_id=session.id,
                role=MessageRole.USER if i % 2 == 0 else MessageRole.ASSISTANT,
                content=f"Message {i}",
                sequence=i + 1,
            )
            db_session.add(message)

        await db_session.commit()
        await db_session.refresh(session)

        # Check relationship
        assert len(session.messages) == 3
