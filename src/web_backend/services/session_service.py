"""
Session service for ArchiFlow Web Backend.

Handles session CRUD operations and lifecycle management.
"""

from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
import logging

from ..models.session import Session, SessionStatus
from ..schemas.session import SessionCreate, SessionUpdate

logger = logging.getLogger(__name__)


class SessionService:
    """Service for managing agent sessions."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        agent_type: str,
        user_prompt: str,
        project_directory: Optional[str] = None,
        user_id: str = "default_user",
    ) -> Session:
        """
        Create a new agent session.

        Args:
            agent_type: Type of agent to run
            user_prompt: Initial prompt for the agent
            project_directory: Optional working directory
            user_id: User ID (default for now)

        Returns:
            Created session object
        """
        session = Session(
            agent_type=agent_type,
            user_prompt=user_prompt,
            project_directory=project_directory,
            user_id=user_id,
            status=SessionStatus.CREATED,
            workflow_state={},
        )

        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)

        logger.info(f"Created session {session.id} for agent type '{agent_type}'")
        return session

    async def get(self, session_id: str) -> Optional[Session]:
        """
        Get a session by ID.

        Args:
            session_id: Session ID to look up

        Returns:
            Session object or None if not found
        """
        result = await self.db.execute(
            select(Session)
            .where(Session.id == session_id)
            .options(selectinload(Session.messages))
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        user_id: Optional[str] = None,
        status: Optional[SessionStatus] = None,
        agent_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[Session], int]:
        """
        List sessions with optional filtering.

        Args:
            user_id: Filter by user ID
            status: Filter by status
            agent_type: Filter by agent type
            page: Page number (1-indexed)
            page_size: Items per page

        Returns:
            Tuple of (sessions list, total count)
        """
        # Build query
        query = select(Session)

        if user_id:
            query = query.where(Session.user_id == user_id)
        if status:
            query = query.where(Session.status == status)
        if agent_type:
            query = query.where(Session.agent_type == agent_type)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination and ordering
        query = query.order_by(Session.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)

        # Execute
        result = await self.db.execute(query)
        sessions = list(result.scalars().all())

        return sessions, total

    async def update(
        self,
        session_id: str,
        update_data: SessionUpdate,
    ) -> Optional[Session]:
        """
        Update a session.

        Args:
            session_id: Session ID to update
            update_data: Fields to update

        Returns:
            Updated session or None if not found
        """
        session = await self.get(session_id)
        if not session:
            return None

        # Update fields
        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            if value is not None:
                setattr(session, field, value)

        await self.db.commit()
        await self.db.refresh(session)

        logger.info(f"Updated session {session_id}")
        return session

    async def update_status(
        self,
        session_id: str,
        status: SessionStatus,
    ) -> Optional[Session]:
        """
        Update session status.

        Args:
            session_id: Session ID
            status: New status

        Returns:
            Updated session or None
        """
        session = await self.get(session_id)
        if not session:
            return None

        session.status = status
        await self.db.commit()
        await self.db.refresh(session)

        logger.info(f"Session {session_id} status changed to {status}")
        return session

    async def delete(self, session_id: str) -> bool:
        """
        Delete a session.

        Args:
            session_id: Session ID to delete

        Returns:
            True if deleted, False if not found
        """
        session = await self.get(session_id)
        if not session:
            return False

        await self.db.delete(session)
        await self.db.commit()

        logger.info(f"Deleted session {session_id}")
        return True

    async def update_workflow_state(
        self,
        session_id: str,
        workflow_state: dict,
    ) -> Optional[Session]:
        """
        Update the workflow state of a session.

        Args:
            session_id: Session ID
            workflow_state: New workflow state

        Returns:
            Updated session or None
        """
        session = await self.get(session_id)
        if not session:
            return None

        session.workflow_state = workflow_state
        await self.db.commit()
        await self.db.refresh(session)

        return session
