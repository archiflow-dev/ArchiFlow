"""
Web Agent Runner for ArchiFlow Web Backend.

Manages agent lifecycle and execution with sandbox enforcement.

This module now supports two execution modes:
1. Broker mode (default): Uses WebSessionBroker for proper tool execution loop
2. Direct mode (legacy): Direct agent.step() calls (for backward compatibility)

Set USE_BROKER_ARCHITECTURE=false to use direct mode.
"""

from typing import Optional, AsyncIterator, Dict, Any, Callable, Awaitable
from pathlib import Path
from datetime import datetime, timezone
import asyncio
import inspect
import logging
import os

from agent_framework.messages.types import BaseMessage, UserMessage, LLMRespondMessage

from .web_context import WebExecutionContext, SandboxMode
from .web_agent_factory import WebAgentFactory
from .workspace_manager import WorkspaceManager
from .storage_manager import StorageManager
from .audit_logger import AuditLogger, AuditEventType
from .web_session_broker import WebSessionBroker, WebSessionBrokerError

if __name__ != "__main__":
    from ..models.session import Session, SessionStatus

logger = logging.getLogger(__name__)


# Feature flag for broker architecture (default: True)
USE_BROKER_ARCHITECTURE = os.getenv("USE_BROKER_ARCHITECTURE", "true").lower() == "true"


class AgentExecutionError(Exception):
    """Raised when agent execution fails."""
    pass


class WebAgentRunner:
    """
    Runs an agent with workspace-sandboxed file operations.

    This is the main integration point between the web backend
    and the agent framework's sandbox system.

    Now supports two modes:
    1. **Broker mode** (default): Uses WebSessionBroker for proper message
       broker integration, enabling:
       - Full tool execution loop (multiple tool calls per message)
       - Auto-refinement of prompts
       - Consistent behavior with CLI
       - Decoupled architecture

    2. **Direct mode** (legacy): Direct agent.step() calls for
       backward compatibility.

    Responsibilities:
    - Creates sandboxed execution context
    - Manages agent lifecycle (start, pause, resume, stop)
    - Handles message passing between user and agent
    - Tracks execution state
    - Provides streaming support for real-time updates

    Usage:
        runner = WebAgentRunner(
            session=session,
            factory=agent_factory,
            message_callback=handle_message
        )

        # Start agent with initial prompt
        await runner.start(user_prompt)

        # Send additional messages
        await runner.send_message("Do something else")

        # Stop when done
        await runner.stop()
    """

    def __init__(
        self,
        session: "Session",
        factory: WebAgentFactory,
        message_callback: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
        use_broker: Optional[bool] = None,
    ):
        """
        Initialize the runner.

        Args:
            session: Database session object
            factory: WebAgentFactory for creating agents
            message_callback: Optional async callback for message events
            use_broker: Override broker mode (default uses USE_BROKER_ARCHITECTURE env)
        """
        self.session = session
        self.factory = factory
        self.message_callback = message_callback

        # Determine broker mode
        self._use_broker = use_broker if use_broker is not None else USE_BROKER_ARCHITECTURE

        # Agent instance (created on start)
        self.agent = None
        self._context: Optional[WebExecutionContext] = None

        # Session broker (only used in broker mode)
        self._session_broker: Optional[WebSessionBroker] = None

        # Execution state
        self._running = False
        self._paused = False
        self._task: Optional[asyncio.Task] = None

        # Message queue for async message passing (used in direct mode)
        self._message_queue: asyncio.Queue = asyncio.Queue()

    @property
    def is_running(self) -> bool:
        """Check if agent is currently running."""
        return self._running and not self._paused

    @property
    def is_paused(self) -> bool:
        """Check if agent is paused."""
        return self._paused

    @property
    def context(self) -> Optional[WebExecutionContext]:
        """Get the execution context."""
        return self._context

    @property
    def workspace_path(self) -> Optional[Path]:
        """Get the workspace path."""
        if self._context:
            return self._context.workspace_path
        return None

    @property
    def session_broker(self) -> Optional[WebSessionBroker]:
        """Get the session broker (if using broker mode)."""
        return self._session_broker

    async def start(self, user_prompt: str) -> None:
        """
        Start the agent with the initial prompt.

        Args:
            user_prompt: Initial user prompt to start the agent

        Raises:
            AgentExecutionError: If agent is already running or creation fails
        """
        if self._running:
            raise AgentExecutionError("Agent is already running")

        try:
            # Create agent with sandboxed tools
            self.agent = await self.factory.create_agent(
                agent_type=self.session.agent_type,
                session_id=self.session.id,
                user_id=self.session.user_id,
            )

            # Store context reference
            self._context = getattr(self.agent, '_web_context', None)

            # Log session start
            if self.factory.audit_logger:
                self.factory.audit_logger.log_session_event(
                    session_id=self.session.id,
                    user_id=self.session.user_id,
                    event_type="session_started",
                    details={
                        "agent_type": self.session.agent_type,
                        "prompt_length": len(user_prompt),
                        "broker_mode": self._use_broker,
                    }
                )

            if self._use_broker:
                # Broker mode: Create and start session broker
                await self._start_with_broker(user_prompt)
            else:
                # Direct mode: Use legacy direct agent.step()
                await self._start_direct(user_prompt)

        except Exception as e:
            logger.exception(f"Failed to start agent for session {self.session.id}")
            self._running = False

            if self.factory.audit_logger:
                self.factory.audit_logger.log_session_event(
                    session_id=self.session.id,
                    user_id=self.session.user_id,
                    event_type="session_error",
                    details={"error": str(e)}
                )

            raise AgentExecutionError(f"Failed to start agent: {e}") from e

    async def _start_with_broker(self, user_prompt: str) -> None:
        """
        Start agent using broker mode.

        Args:
            user_prompt: Initial user prompt
        """
        logger.info("=" * 60)
        logger.info(f"🚀 [AgentRunner] Starting agent in broker mode")
        logger.info(f"   Session: {self.session.id}")
        logger.info(f"   Agent type: {self.session.agent_type}")
        logger.info(f"   Prompt: {user_prompt[:100]}...")
        logger.info("=" * 60)

        # Create session broker
        workspace = self._context.workspace_path if self._context else Path.cwd()

        logger.info(f"📁 [AgentRunner] Workspace: {workspace}")

        self._session_broker = WebSessionBroker(
            session_id=self.session.id,
            user_id=self.session.user_id,
            agent=self.agent,
            workspace_path=workspace,
            ws_callback=self._forward_to_callback,
            auto_refine_enabled=os.getenv("AUTO_REFINE_PROMPTS", "false").lower() == "true",
        )

        logger.info(f"🔧 [AgentRunner] Session broker created, starting...")

        # Start broker infrastructure
        await self._session_broker.start()

        logger.info(f"✅ [AgentRunner] Broker started successfully")

        self._running = True

        # Emit start event
        await self._emit_event("agent_started", {
            "session_id": self.session.id,
            "agent_type": self.session.agent_type,
            "mode": "broker",
        })

        logger.info(f"📤 [AgentRunner] Sending initial prompt to broker...")

        # Send initial prompt via broker
        await self._session_broker.send_message(user_prompt)

        logger.info(
            f"✅ [AgentRunner] Started agent with broker for session {self.session.id} "
            f"(agent_type={self.session.agent_type})"
        )

    async def _start_direct(self, user_prompt: str) -> None:
        """
        Start agent using direct mode (legacy).

        Args:
            user_prompt: Initial user prompt
        """
        self._running = True

        # Notify via callback
        await self._emit_event("agent_started", {
            "session_id": self.session.id,
            "agent_type": self.session.agent_type,
            "mode": "direct",
        })

        # Run the agent step with initial prompt
        await self._run_agent_step(user_prompt)

        logger.info(
            f"Started agent with direct mode for session {self.session.id} "
            f"(agent_type={self.session.agent_type})"
        )

    async def _forward_to_callback(self, event: Dict[str, Any]) -> None:
        """
        Forward broker events to the message callback.

        Args:
            event: Event from session broker
        """
        if self.message_callback:
            try:
                # Add timestamp if not present
                if "timestamp" not in event:
                    event["timestamp"] = datetime.now(timezone.utc).isoformat()
                await self.message_callback(event)
            except Exception as e:
                logger.warning(f"Error in message callback: {e}")

    async def send_message(self, content: str) -> None:
        """
        Send a message to the running agent.

        Args:
            content: Message content

        Raises:
            AgentExecutionError: If agent is not running
        """
        logger.info("=" * 60)
        logger.info(f"📨 [AgentRunner] send_message called")
        logger.info(f"   Session: {self.session.id}")
        logger.info(f"   Content: {content[:100]}...")
        logger.info(f"   Running: {self._running}")
        logger.info(f"   Paused: {self._paused}")
        logger.info(f"   Broker mode: {self._use_broker}")
        logger.info("=" * 60)

        if not self._running:
            error_msg = "Agent is not running"
            logger.error(f"❌ [AgentRunner] {error_msg}")
            raise AgentExecutionError(error_msg)

        if self._paused:
            error_msg = "Agent is paused"
            logger.error(f"❌ [AgentRunner] {error_msg}")
            raise AgentExecutionError(error_msg)

        if self._use_broker and self._session_broker:
            # Broker mode: Send via broker
            logger.info(f"🔄 [AgentRunner] Sending via session broker...")
            await self._session_broker.send_message(content)
            logger.info(f"✅ [AgentRunner] Message sent to broker successfully")
        else:
            # Direct mode: Run agent step
            logger.info(f"🔄 [AgentRunner] Running agent step (direct mode)...")
            await self._run_agent_step(content)
            logger.info(f"✅ [AgentRunner] Agent step completed")

    async def pause(self) -> None:
        """Pause agent execution."""
        if not self._running:
            return

        self._paused = True

        await self._emit_event("agent_paused", {
            "session_id": self.session.id,
        })

        if self.factory.audit_logger:
            self.factory.audit_logger.log_session_event(
                session_id=self.session.id,
                user_id=self.session.user_id,
                event_type="session_paused",
                details={}
            )

    async def resume(self) -> None:
        """Resume paused agent execution."""
        if not self._paused:
            return

        self._paused = False

        await self._emit_event("agent_resumed", {
            "session_id": self.session.id,
        })

        if self.factory.audit_logger:
            self.factory.audit_logger.log_session_event(
                session_id=self.session.id,
                user_id=self.session.user_id,
                event_type="session_resumed",
                details={}
            )

    async def stop(self) -> None:
        """Stop agent execution."""
        if not self._running:
            return

        self._running = False
        self._paused = False

        # Stop broker if using broker mode
        if self._session_broker:
            try:
                await self._session_broker.stop()
            except Exception as e:
                logger.warning(f"Error stopping session broker: {e}")
            finally:
                self._session_broker = None

        # Cancel any pending task
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        await self._emit_event("agent_stopped", {
            "session_id": self.session.id,
        })

        if self.factory.audit_logger:
            self.factory.audit_logger.log_session_event(
                session_id=self.session.id,
                user_id=self.session.user_id,
                event_type="session_stopped",
                details={}
            )

    async def _run_agent_step(self, user_input: str) -> None:
        """
        Run a single agent step with user input (direct mode only).

        Args:
            user_input: User message content
        """
        if not self.agent:
            raise AgentExecutionError("Agent not initialized")

        try:
            # Create user message
            user_message = UserMessage(
                session_id=self.session.id,
                content=user_input,
                sequence=0,  # Agent will handle sequencing
            )

            # Emit user message event
            await self._emit_event("user_message", {
                "session_id": self.session.id,
                "content": user_input,
            })

            # Run agent step
            response = await self._execute_agent_step(user_message)

            # Emit response event
            if response:
                await self._emit_event("agent_message", {
                    "session_id": self.session.id,
                    "content": str(response.content) if hasattr(response, 'content') else str(response),
                    "type": type(response).__name__,
                })

        except Exception as e:
            logger.exception(f"Error in agent step for session {self.session.id}")
            await self._emit_event("agent_error", {
                "session_id": self.session.id,
                "error": str(e),
            })
            raise

    async def _execute_agent_step(self, message: BaseMessage) -> Optional[BaseMessage]:
        """
        Execute a single agent step (direct mode only).

        Args:
            message: Input message

        Returns:
            Agent response message
        """
        # Check if agent has async step method
        if hasattr(self.agent, 'step'):
            if inspect.iscoroutinefunction(self.agent.step):
                return await self.agent.step(message)
            else:
                # Run sync step in executor
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(None, self.agent.step, message)

        # Fallback: try run method
        if hasattr(self.agent, 'run'):
            if inspect.iscoroutinefunction(self.agent.run):
                return await self.agent.run(message.content if hasattr(message, 'content') else str(message))
            else:
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    None,
                    self.agent.run,
                    message.content if hasattr(message, 'content') else str(message)
                )

        raise AgentExecutionError("Agent has no step or run method")

    async def _emit_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        Emit an event via the callback.

        Args:
            event_type: Type of event
            data: Event data
        """
        if self.message_callback:
            try:
                await self.message_callback({
                    "type": event_type,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    **data
                })
            except Exception as e:
                logger.warning(f"Error in message callback: {e}")

    def get_conversation_history(self) -> list:
        """
        Get the conversation history from the agent.

        Returns:
            List of messages
        """
        if self.agent and hasattr(self.agent, 'history'):
            return list(self.agent.history.messages)
        return []

    def get_execution_stats(self) -> Dict[str, Any]:
        """
        Get execution statistics.

        Returns:
            Dictionary with execution stats
        """
        stats = {
            "session_id": self.session.id,
            "agent_type": self.session.agent_type,
            "is_running": self._running,
            "is_paused": self._paused,
            "mode": "broker" if self._use_broker else "direct",
        }

        if self._context:
            stats["workspace"] = str(self._context.workspace_path)
            stats["sandbox_mode"] = self._context.sandbox_mode.value

        if self.agent and hasattr(self.agent, 'history'):
            stats["message_count"] = len(self.agent.history.messages)

        # Add broker stats if available
        if self._session_broker:
            stats["broker_stats"] = self._session_broker.get_stats()

        return stats


class AgentRunnerPool:
    """
    Pool of active agent runners.

    Manages multiple concurrent agent sessions.
    """

    def __init__(self, max_runners: int = 100):
        """
        Initialize the pool.

        Args:
            max_runners: Maximum concurrent runners
        """
        self.max_runners = max_runners
        self._runners: Dict[str, WebAgentRunner] = {}
        self._lock = asyncio.Lock()

    async def get(self, session_id: str) -> Optional[WebAgentRunner]:
        """Get a runner by session ID."""
        async with self._lock:
            return self._runners.get(session_id)

    async def add(self, runner: WebAgentRunner) -> None:
        """Add a runner to the pool."""
        async with self._lock:
            if len(self._runners) >= self.max_runners:
                raise AgentExecutionError(f"Maximum runners ({self.max_runners}) reached")
            self._runners[runner.session.id] = runner

    async def remove(self, session_id: str) -> Optional[WebAgentRunner]:
        """Remove a runner from the pool."""
        async with self._lock:
            return self._runners.pop(session_id, None)

    async def stop_all(self) -> None:
        """Stop all runners."""
        async with self._lock:
            for runner in self._runners.values():
                try:
                    await runner.stop()
                except Exception as e:
                    logger.warning(f"Error stopping runner: {e}")
            self._runners.clear()

    def list_active(self) -> list:
        """List active session IDs."""
        return list(self._runners.keys())

    def count(self) -> int:
        """Get count of active runners."""
        return len(self._runners)


# Global runner pool instance
_runner_pool: Optional[AgentRunnerPool] = None


def get_runner_pool() -> AgentRunnerPool:
    """Get the global runner pool."""
    global _runner_pool
    if _runner_pool is None:
        _runner_pool = AgentRunnerPool()
    return _runner_pool
