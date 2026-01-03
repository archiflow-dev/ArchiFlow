"""
Session Store for ArchiFlow Web Backend.

Provides a simple interface to access session data without
requiring FastAPI dependency injection.
"""

from typing import Optional
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
import logging

from ..config import settings

logger = logging.getLogger(__name__)


@dataclass
class SessionInfo:
    """Minimal session info needed by other services."""
    id: str
    agent_type: str
    user_id: str
    status: str
    project_directory: Optional[str] = None


class SessionStore:
    """
    Simple session store that provides access to session data.

    This is used by services that need to look up session information
    without going through the full SessionService.
    """

    def __init__(self):
        """Initialize the session store."""
        self._engine = None
        self._session_factory = None

    async def _get_engine(self):
        """Lazy initialization of database engine."""
        if self._engine is None:
            from ..database.connection import engine
            self._engine = engine
            self._session_factory = sessionmaker(
                self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
        return self._engine

    async def get(self, session_id: str) -> Optional[SessionInfo]:
        """
        Get session info by ID.

        Args:
            session_id: Session ID

        Returns:
            SessionInfo or None if not found
        """
        await self._get_engine()

        from ..models.session import Session

        async with self._session_factory() as db:
            result = await db.execute(
                select(Session).where(Session.id == session_id)
            )
            session = result.scalar_one_or_none()

            if not session:
                return None

            return SessionInfo(
                id=session.id,
                agent_type=session.agent_type,
                user_id=session.user_id,
                status=session.status.value,
                project_directory=session.project_directory,
            )

    async def exists(self, session_id: str) -> bool:
        """Check if a session exists."""
        session = await self.get(session_id)
        return session is not None


# Global singleton instance
_session_store: Optional[SessionStore] = None


def get_session_store() -> SessionStore:
    """Get the global SessionStore instance."""
    global _session_store
    if _session_store is None:
        _session_store = SessionStore()
    return _session_store
