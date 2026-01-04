"""
Agent Session Manager for ArchiFlow Web Backend.

Manages agent instances with database-backed session persistence.
Provides the integration layer between web API and agent framework.
"""

from typing import Optional, Dict, Any, Callable, Awaitable, List
from datetime import datetime, timezone
import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from .web_agent_factory import WebAgentFactory, get_web_agent_factory
from .agent_runner import WebAgentRunner, AgentRunnerPool, get_runner_pool, AgentExecutionError
from .workspace_manager import WorkspaceManager, get_workspace_manager
from .storage_manager import StorageManager, get_storage_manager
from .audit_logger import AuditLogger

if __name__ != "__main__":
    from ..models.session import Session, SessionStatus
    from ..services.session_service import SessionService

logger = logging.getLogger(__name__)


class AgentSessionManager:
    """
    Manages agent sessions with database persistence.

    This is the main entry point for the web API to interact with agents.
    It provides:
    - Session creation with workspace setup
    - Agent lifecycle management (start, stop, pause, resume)
    - Message passing to running agents
    - Session persistence and recovery
    - History reconstruction for reconnecting users

    Usage:
        manager = AgentSessionManager(db_session, factory)

        # Create a new session
        session = await manager.create_session(
            agent_type="coding",
            user_id="user_123",
            user_prompt="Build a web app"
        )

        # Start the agent
        await manager.start_session(session.id)

        # Send messages
        await manager.send_message(session.id, "Add a login page")

        # User reconnects - get runner for existing session
        runner = await manager.get_or_create_runner(session.id)
    """

    def __init__(
        self,
        db: AsyncSession,
        factory: Optional[WebAgentFactory] = None,
        runner_pool: Optional[AgentRunnerPool] = None,
        use_broker: Optional[bool] = None,
    ):
        """
        Initialize the session manager.

        Args:
            db: SQLAlchemy async session
            factory: WebAgentFactory instance (uses global if not provided)
            runner_pool: Runner pool (uses global if not provided)
            use_broker: Whether to use broker mode for runners (default: env setting)
        """
        self.db = db
        self.factory = factory or get_web_agent_factory()
        self.runner_pool = runner_pool or get_runner_pool()
        self.session_service = SessionService(db)
        self._use_broker = use_broker

    async def create_session(
        self,
        agent_type: str,
        user_id: str,
        user_prompt: str,
        project_directory: Optional[str] = None,
        auto_start: bool = False,
    ) -> "Session":
        """
        Create a new agent session.

        Args:
            agent_type: Type of agent (coding, comic, ppt, etc.)
            user_id: User identifier
            user_prompt: Initial prompt
            project_directory: Ignored for web (workspace used instead)
            auto_start: Whether to start the agent immediately

        Returns:
            Created session object
        """
        # Check session limit
        if self.factory.storage_manager:
            session_count = self.factory.storage_manager.get_user_session_count(user_id)
            max_sessions = self.factory.storage_manager.limits.max_sessions_per_user
            if session_count >= max_sessions:
                raise AgentExecutionError(
                    f"Maximum sessions ({max_sessions}) reached for user"
                )

        # Create session in database
        session = await self.session_service.create(
            agent_type=agent_type,
            user_prompt=user_prompt,
            user_id=user_id,
        )

        # Create workspace
        workspace_path = self.factory.workspace_manager.create_workspace(
            user_id, session.id
        )

        # Update session with workspace path
        session.workspace_path = str(workspace_path)
        await self.db.commit()

        logger.info(f"Created session {session.id} for user {user_id}")

        # Auto-start if requested
        if auto_start:
            await self.start_session(session.id, user_prompt)

        return session

    async def get_session(self, session_id: str) -> Optional["Session"]:
        """Get a session by ID."""
        return await self.session_service.get(session_id)

    async def start_session(
        self,
        session_id: str,
        initial_prompt: Optional[str] = None,
        message_callback: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
    ) -> WebAgentRunner:
        """
        Start a session's agent.

        Args:
            session_id: Session to start
            initial_prompt: Optional override for initial prompt
            message_callback: Callback for real-time message events

        Returns:
            The WebAgentRunner instance

        Raises:
            AgentExecutionError: If session not found or already running
        """
        session = await self.get_session(session_id)
        if not session:
            raise AgentExecutionError(f"Session {session_id} not found")

        # Check if already running
        existing_runner = await self.runner_pool.get(session_id)
        if existing_runner and existing_runner.is_running:
            raise AgentExecutionError(f"Session {session_id} is already running")

        # Create runner
        runner = WebAgentRunner(
            session=session,
            factory=self.factory,
            message_callback=message_callback,
            use_broker=self._use_broker,
        )

        # Add to pool
        await self.runner_pool.add(runner)

        # Start agent
        prompt = initial_prompt or session.user_prompt
        await runner.start(prompt)

        # Update session status
        await self.session_service.update_status(session_id, SessionStatus.RUNNING)

        return runner

    async def get_or_create_runner(
        self,
        session_id: str,
        message_callback: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
    ) -> WebAgentRunner:
        """
        Get existing runner or create new one for session.

        This is used when a user reconnects to an existing session.
        If the agent was running, it returns the existing runner.
        If not, it creates a new runner (but doesn't start it).

        Args:
            session_id: Session ID
            message_callback: Callback for message events

        Returns:
            WebAgentRunner instance
        """
        # Check pool first
        runner = await self.runner_pool.get(session_id)
        if runner:
            # Update callback if provided
            if message_callback:
                runner.message_callback = message_callback
            return runner

        # Get session from database
        session = await self.get_session(session_id)
        if not session:
            raise AgentExecutionError(f"Session {session_id} not found")

        # Create new runner (not started)
        runner = WebAgentRunner(
            session=session,
            factory=self.factory,
            message_callback=message_callback,
            use_broker=self._use_broker,
        )

        # Add to pool
        await self.runner_pool.add(runner)

        return runner

    async def send_message(
        self,
        session_id: str,
        content: str,
    ) -> None:
        """
        Send a message to a running agent.

        Args:
            session_id: Session ID
            content: Message content

        Raises:
            AgentExecutionError: If session not running
        """
        runner = await self.runner_pool.get(session_id)
        if not runner:
            raise AgentExecutionError(f"Session {session_id} is not active")

        if not runner.is_running:
            raise AgentExecutionError(f"Session {session_id} is not running")

        await runner.send_message(content)

    async def pause_session(self, session_id: str) -> None:
        """Pause a running session."""
        runner = await self.runner_pool.get(session_id)
        if runner:
            await runner.pause()
            await self.session_service.update_status(session_id, SessionStatus.PAUSED)

    async def resume_session(self, session_id: str) -> None:
        """Resume a paused session."""
        runner = await self.runner_pool.get(session_id)
        if runner:
            await runner.resume()
            await self.session_service.update_status(session_id, SessionStatus.RUNNING)

    async def stop_session(self, session_id: str) -> None:
        """Stop a running session."""
        runner = await self.runner_pool.remove(session_id)
        if runner:
            await runner.stop()
            await self.session_service.update_status(session_id, SessionStatus.COMPLETED)

    async def delete_session(
        self,
        session_id: str,
        delete_workspace: bool = True,
    ) -> bool:
        """
        Delete a session.

        Args:
            session_id: Session to delete
            delete_workspace: Whether to delete the workspace files

        Returns:
            True if deleted
        """
        # Stop if running
        await self.stop_session(session_id)

        # Get session for workspace info
        session = await self.get_session(session_id)
        if not session:
            return False

        # Delete workspace if requested
        if delete_workspace and session.workspace_path:
            self.factory.workspace_manager.delete_workspace(
                session.user_id, session_id
            )

        # Delete from database
        return await self.session_service.delete(session_id)

    async def get_session_history(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Get conversation history for a session.

        This retrieves messages from the database, not from the in-memory agent.
        Used for displaying history when reconnecting.

        Args:
            session_id: Session ID

        Returns:
            List of message dictionaries
        """
        session = await self.session_service.get(session_id)
        if not session:
            return []

        return [msg.to_dict() for msg in session.messages]

    async def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """
        Get detailed status of a session.

        Args:
            session_id: Session ID

        Returns:
            Status dictionary
        """
        session = await self.get_session(session_id)
        if not session:
            return {"error": "Session not found"}

        status = {
            "session_id": session_id,
            "agent_type": session.agent_type,
            "status": session.status.value if hasattr(session.status, 'value') else str(session.status) if session.status else "unknown",
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "updated_at": session.updated_at.isoformat() if session.updated_at else None,
        }

        # Add runner info if active
        runner = await self.runner_pool.get(session_id)
        if runner:
            status.update({
                "is_running": runner.is_running,
                "is_paused": runner.is_paused,
                "execution_stats": runner.get_execution_stats(),
            })
        else:
            status.update({
                "is_running": False,
                "is_paused": False,
            })

        # Add workspace info
        if session.workspace_path:
            status["workspace_path"] = session.workspace_path
            try:
                usage = self.factory.storage_manager.get_workspace_usage(
                    session.user_id, session_id
                ) if self.factory.storage_manager else {}
                status["workspace_usage"] = usage
            except Exception:
                pass

        return status

    async def list_user_sessions(
        self,
        user_id: str,
        include_active_status: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        List all sessions for a user.

        Args:
            user_id: User ID
            include_active_status: Whether to include running status

        Returns:
            List of session info dictionaries
        """
        sessions, _ = await self.session_service.list(user_id=user_id)

        results = []
        for session in sessions:
            info = session.to_dict()

            if include_active_status:
                runner = await self.runner_pool.get(session.id)
                info["is_active"] = runner is not None and runner.is_running

            results.append(info)

        return results

    async def cleanup_inactive_sessions(
        self,
        max_idle_minutes: int = 60,
    ) -> int:
        """
        Clean up sessions that have been idle too long.

        Args:
            max_idle_minutes: Maximum idle time before cleanup

        Returns:
            Number of sessions cleaned up
        """
        count = 0
        # This would scan for idle sessions and clean them up
        # Implementation depends on tracking last activity time
        return count


# Dependency injection helper
async def get_agent_session_manager(
    db: AsyncSession,
) -> AgentSessionManager:
    """
    Create an AgentSessionManager for dependency injection.

    Usage in FastAPI:
        @router.post("/sessions")
        async def create(
            data: SessionCreate,
            manager: AgentSessionManager = Depends(get_agent_session_manager)
        ):
            return await manager.create_session(...)
    """
    return AgentSessionManager(db)
