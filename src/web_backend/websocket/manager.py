"""
WebSocket connection manager.

Manages connected clients and session subscriptions.
"""

from typing import Dict, Set, Optional
from dataclasses import dataclass, field
import logging
import asyncio

logger = logging.getLogger(__name__)


@dataclass
class ClientInfo:
    """Information about a connected client."""
    sid: str
    user_id: Optional[str] = None
    subscribed_sessions: Set[str] = field(default_factory=set)
    connected_at: float = 0.0


class ConnectionManager:
    """
    Manages WebSocket connections and session subscriptions.

    Clients can subscribe to session updates to receive real-time events.
    """

    def __init__(self):
        # Maps session ID (sid) to client info
        self._clients: Dict[str, ClientInfo] = {}

        # Maps session ID to set of subscribed client sids
        self._session_subscribers: Dict[str, Set[str]] = {}

        # Lock for thread-safe operations
        self._lock = asyncio.Lock()

    async def connect(self, sid: str, user_id: Optional[str] = None) -> None:
        """
        Register a new client connection.

        Args:
            sid: Socket.IO session ID
            user_id: Optional user ID
        """
        async with self._lock:
            import time
            self._clients[sid] = ClientInfo(
                sid=sid,
                user_id=user_id,
                connected_at=time.time()
            )
            logger.info(f"Client connected: {sid}")

    async def disconnect(self, sid: str) -> None:
        """
        Handle client disconnection.

        Removes client from all session subscriptions.
        """
        async with self._lock:
            if sid in self._clients:
                client = self._clients[sid]

                # Remove from all session subscriptions
                for session_id in client.subscribed_sessions:
                    if session_id in self._session_subscribers:
                        self._session_subscribers[session_id].discard(sid)
                        # Clean up empty subscription sets
                        if not self._session_subscribers[session_id]:
                            del self._session_subscribers[session_id]

                del self._clients[sid]
                logger.info(f"Client disconnected: {sid}")

    async def subscribe_to_session(self, sid: str, session_id: str) -> bool:
        """
        Subscribe a client to a session's updates.

        Args:
            sid: Client session ID
            session_id: Session ID to subscribe to

        Returns:
            True if subscription successful
        """
        async with self._lock:
            if sid not in self._clients:
                logger.warning(f"Unknown client tried to subscribe: {sid}")
                return False

            # Add to client's subscriptions
            self._clients[sid].subscribed_sessions.add(session_id)

            # Add to session's subscribers
            if session_id not in self._session_subscribers:
                self._session_subscribers[session_id] = set()
            self._session_subscribers[session_id].add(sid)

            logger.info(f"Client {sid} subscribed to session {session_id}")
            return True

    async def unsubscribe_from_session(self, sid: str, session_id: str) -> bool:
        """
        Unsubscribe a client from a session's updates.

        Args:
            sid: Client session ID
            session_id: Session ID to unsubscribe from

        Returns:
            True if unsubscription successful
        """
        async with self._lock:
            if sid not in self._clients:
                return False

            # Remove from client's subscriptions
            self._clients[sid].subscribed_sessions.discard(session_id)

            # Remove from session's subscribers
            if session_id in self._session_subscribers:
                self._session_subscribers[session_id].discard(sid)
                if not self._session_subscribers[session_id]:
                    del self._session_subscribers[session_id]

            logger.info(f"Client {sid} unsubscribed from session {session_id}")
            return True

    def get_session_subscribers(self, session_id: str) -> Set[str]:
        """
        Get all clients subscribed to a session.

        Args:
            session_id: Session ID

        Returns:
            Set of client sids subscribed to the session
        """
        return self._session_subscribers.get(session_id, set()).copy()

    def get_client_info(self, sid: str) -> Optional[ClientInfo]:
        """Get information about a connected client."""
        return self._clients.get(sid)

    @property
    def connected_clients(self) -> int:
        """Get number of connected clients."""
        return len(self._clients)

    @property
    def active_sessions(self) -> int:
        """Get number of sessions with active subscribers."""
        return len(self._session_subscribers)


# Global connection manager instance
connection_manager = ConnectionManager()
