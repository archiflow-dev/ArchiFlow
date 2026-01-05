"""
Socket.IO server for real-time communication.

Handles WebSocket connections and events.
"""

import socketio
import logging
from typing import Optional

from ..config import settings
from .manager import connection_manager

logger = logging.getLogger(__name__)

# Create Socket.IO async server
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins=settings.CORS_ORIGINS,
    ping_interval=settings.WEBSOCKET_PING_INTERVAL,
    ping_timeout=settings.WEBSOCKET_PING_TIMEOUT,
    logger=settings.DEBUG,
    engineio_logger=settings.DEBUG,
)


# Connection events
@sio.event
async def connect(sid: str, environ: dict, auth: Optional[dict] = None):
    """
    Handle new WebSocket connection.

    Args:
        sid: Socket.IO session ID
        environ: WSGI environment
        auth: Optional authentication data
    """
    logger.info(f"Client connecting: {sid}")

    # Extract user ID from auth if provided
    user_id = auth.get("user_id") if auth else None

    await connection_manager.connect(sid, user_id)

    # Send welcome message
    await sio.emit('connected', {
        'sid': sid,
        'message': 'Connected to ArchiFlow WebSocket server'
    }, to=sid)


@sio.event
async def disconnect(sid: str):
    """Handle WebSocket disconnection."""
    logger.info(f"Client disconnecting: {sid}")
    await connection_manager.disconnect(sid)


# Session subscription events
@sio.event
async def subscribe_session(sid: str, data: dict):
    """
    Subscribe to a session's updates.

    Args:
        sid: Client session ID
        data: Should contain 'session_id'
    """
    session_id = data.get('session_id')
    if not session_id:
        await sio.emit('error', {
            'message': 'session_id is required'
        }, to=sid)
        return

    success = await connection_manager.subscribe_to_session(sid, session_id)

    if success:
        # Join the Socket.IO room for this session
        await sio.enter_room(sid, f"session:{session_id}")

        await sio.emit('subscribed', {
            'session_id': session_id,
            'message': f'Subscribed to session {session_id}'
        }, to=sid)

        logger.info(f"Client {sid} subscribed to session {session_id}")
    else:
        await sio.emit('error', {
            'message': 'Failed to subscribe to session'
        }, to=sid)


@sio.event
async def unsubscribe_session(sid: str, data: dict):
    """
    Unsubscribe from a session's updates.

    Args:
        sid: Client session ID
        data: Should contain 'session_id'
    """
    session_id = data.get('session_id')
    if not session_id:
        await sio.emit('error', {
            'message': 'session_id is required'
        }, to=sid)
        return

    success = await connection_manager.unsubscribe_from_session(sid, session_id)

    if success:
        # Leave the Socket.IO room for this session
        await sio.leave_room(sid, f"session:{session_id}")

        await sio.emit('unsubscribed', {
            'session_id': session_id,
            'message': f'Unsubscribed from session {session_id}'
        }, to=sid)


# Ping/pong for keep-alive
@sio.event
async def ping(sid: str, data: dict = None):
    """Handle ping from client."""
    await sio.emit('pong', {'timestamp': data.get('timestamp') if data else None}, to=sid)


# Message event - handles user chat messages
@sio.event
async def message(sid: str, data: dict):
    """
    Handle message from client.

    Expected data format:
    {
        "type": "message",
        "content": "user message here",
        "session_id": "session-uuid"
    }
    """
    import asyncio
    from ..services.agent_session_manager import get_agent_session_manager
    from ..database.connection import async_session_factory

    logger.info("=" * 60)
    logger.info("📨 [WebSocket] Received message event")
    logger.info(f"   SID (socket): {sid}")
    logger.info(f"   Data type: {data.get('type')}")
    logger.info(f"   Session ID: {data.get('session_id')}")
    logger.info(f"   Content: {data.get('content', '')[:100]}...")
    logger.info("=" * 60)

    msg_type = data.get('type')
    session_id = data.get('session_id')
    content = data.get('content', '')

    if not session_id:
        logger.error("❌ Missing session_id in message")
        await sio.emit('error', {
            'message': 'session_id is required'
        }, to=sid)
        return

    if msg_type != 'message':
        logger.warning(f"⚠️ Unexpected message type: {msg_type}")
        return

    if not content:
        logger.warning("⚠️ Empty message content, ignoring")
        return

    try:
        # Create database session
        async with async_session_factory() as db:
            manager = await get_agent_session_manager(db)

            logger.info(f"🔄 [WebSocket] Getting runner for session {session_id}")

            # Get or create runner for this session
            runner = await manager.get_or_create_runner(session_id)

            logger.info(f"✅ [WebSocket] Runner obtained: running={runner.is_running}")

            # Check if runner is running
            if not runner.is_running:
                logger.warning(f"⚠️ [WebSocket] Runner not running, starting...")
                session = await manager.get_session(session_id)
                await runner.start(session.user_prompt)
                logger.info(f"✅ [WebSocket] Runner started")

            # Send the message to the agent
            logger.info(f"📤 [WebSocket] Sending message to agent runner...")
            await runner.send_message(content)
            logger.info(f"✅ [WebSocket] Message sent to agent successfully")

    except Exception as e:
        logger.exception(f"❌ [WebSocket] Error processing message: {e}")
        await sio.emit('error', {
            'message': f'Failed to process message: {str(e)}'
        }, to=sid)


# Helper functions for emitting events to sessions
async def emit_to_session(session_id: str, event: str, data: dict):
    """
    Emit an event to all clients subscribed to a session.

    Args:
        session_id: Session ID
        event: Event name
        data: Event data
    """
    room = f"session:{session_id}"
    await sio.emit(event, data, room=room)


async def emit_agent_event(session_id: str, event_type: str, payload: dict):
    """
    Emit an agent event to subscribed clients.

    Args:
        session_id: Session ID
        event_type: Type of agent event
        payload: Event payload
    """
    await emit_to_session(session_id, 'agent_event', {
        'type': event_type,
        'session_id': session_id,
        'payload': payload
    })


async def emit_workflow_update(session_id: str, workflow_state: dict):
    """
    Emit a workflow state update to subscribed clients.

    Args:
        session_id: Session ID
        workflow_state: Current workflow state
    """
    await emit_to_session(session_id, 'workflow_update', {
        'session_id': session_id,
        'workflow_state': workflow_state
    })


async def emit_artifact_update(session_id: str, artifact_path: str, action: str):
    """
    Emit an artifact update to subscribed clients.

    Args:
        session_id: Session ID
        artifact_path: Path to the artifact
        action: Action performed (created, updated, deleted)
    """
    await emit_to_session(session_id, 'artifact_update', {
        'session_id': session_id,
        'artifact_path': artifact_path,
        'action': action
    })


async def emit_message(session_id: str, message: dict):
    """
    Emit a new message to subscribed clients.

    Args:
        session_id: Session ID
        message: Message data
    """
    await emit_to_session(session_id, 'message', {
        'session_id': session_id,
        'message': message
    })


# Create ASGI app that wraps Socket.IO
# This will be used to mount Socket.IO on the FastAPI app
socket_app = socketio.ASGIApp(sio)
