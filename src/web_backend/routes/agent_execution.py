"""
Agent Execution API routes.

Handles agent lifecycle and message passing for running sessions.
"""

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import asyncio
import logging

from ..database.connection import get_db
from ..services.agent_session_manager import AgentSessionManager, get_agent_session_manager
from ..services.agent_runner import AgentExecutionError
from ..models.session import SessionStatus

logger = logging.getLogger(__name__)

router = APIRouter()


# Request/Response Schemas

class StartSessionRequest(BaseModel):
    """Request to start a session's agent."""
    initial_prompt: Optional[str] = Field(
        None,
        description="Override the session's initial prompt"
    )


class SendMessageRequest(BaseModel):
    """Request to send a message to a running agent."""
    content: str = Field(..., description="Message content")


class SessionStatusResponse(BaseModel):
    """Response with session status."""
    session_id: str
    agent_type: str
    status: str
    is_running: bool
    is_paused: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    workspace_path: Optional[str] = None
    workspace_usage: Optional[Dict[str, Any]] = None
    execution_stats: Optional[Dict[str, Any]] = None


class MessageResponse(BaseModel):
    """Response for a message operation."""
    success: bool
    message: Optional[str] = None


class HistoryMessage(BaseModel):
    """A message in the conversation history."""
    id: str
    role: str
    content: str
    sequence: int
    tool_name: Optional[str] = None
    created_at: Optional[str] = None


class HistoryResponse(BaseModel):
    """Response with conversation history."""
    session_id: str
    messages: List[HistoryMessage]
    total: int


# Dependency for session manager
async def get_manager(
    db: AsyncSession = Depends(get_db)
) -> AgentSessionManager:
    """Get AgentSessionManager dependency."""
    return await get_agent_session_manager(db)


# Routes

@router.post("/{session_id}/start", response_model=SessionStatusResponse)
async def start_session(
    session_id: str,
    request: Optional[StartSessionRequest] = None,
    manager: AgentSessionManager = Depends(get_manager),
):
    """
    Start a session's agent.

    This creates the agent instance and begins processing.
    The agent will use the session's initial prompt unless overridden.
    """
    try:
        initial_prompt = request.initial_prompt if request else None
        await manager.start_session(session_id, initial_prompt)

        status = await manager.get_session_status(session_id)
        return SessionStatusResponse(**status)

    except AgentExecutionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Error starting session {session_id}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{session_id}/stop", response_model=MessageResponse)
async def stop_session(
    session_id: str,
    manager: AgentSessionManager = Depends(get_manager),
):
    """
    Stop a running session's agent.

    The agent will be stopped and the session marked as completed.
    """
    try:
        await manager.stop_session(session_id)
        return MessageResponse(success=True, message="Session stopped")

    except AgentExecutionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Error stopping session {session_id}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{session_id}/pause", response_model=MessageResponse)
async def pause_session(
    session_id: str,
    manager: AgentSessionManager = Depends(get_manager),
):
    """
    Pause a running session.

    The agent will stop processing but can be resumed later.
    """
    try:
        await manager.pause_session(session_id)
        return MessageResponse(success=True, message="Session paused")

    except AgentExecutionError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{session_id}/resume", response_model=MessageResponse)
async def resume_session(
    session_id: str,
    manager: AgentSessionManager = Depends(get_manager),
):
    """
    Resume a paused session.

    The agent will continue processing from where it left off.
    """
    try:
        await manager.resume_session(session_id)
        return MessageResponse(success=True, message="Session resumed")

    except AgentExecutionError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{session_id}/message", response_model=MessageResponse)
async def send_message(
    session_id: str,
    request: SendMessageRequest,
    manager: AgentSessionManager = Depends(get_manager),
):
    """
    Send a message to a running agent.

    The agent must be running (not paused or stopped).
    """
    try:
        await manager.send_message(session_id, request.content)
        return MessageResponse(success=True, message="Message sent")

    except AgentExecutionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Error sending message to session {session_id}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}/status", response_model=SessionStatusResponse)
async def get_session_status(
    session_id: str,
    manager: AgentSessionManager = Depends(get_manager),
):
    """
    Get detailed status of a session.

    Returns running status, workspace usage, and execution stats.
    """
    try:
        status = await manager.get_session_status(session_id)

        if "error" in status:
            raise HTTPException(status_code=404, detail=status["error"])

        return SessionStatusResponse(**status)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting status for session {session_id}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}/history", response_model=HistoryResponse)
async def get_session_history(
    session_id: str,
    manager: AgentSessionManager = Depends(get_manager),
):
    """
    Get conversation history for a session.

    Returns all messages in the session, ordered by sequence.
    """
    try:
        messages = await manager.get_session_history(session_id)

        return HistoryResponse(
            session_id=session_id,
            messages=[HistoryMessage(**msg) for msg in messages],
            total=len(messages),
        )

    except Exception as e:
        logger.exception(f"Error getting history for session {session_id}")
        raise HTTPException(status_code=500, detail=str(e))


# WebSocket for real-time updates

class ConnectionManager:
    """Manages WebSocket connections for sessions."""

    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        """Connect a WebSocket to a session."""
        await websocket.accept()
        if session_id not in self.active_connections:
            self.active_connections[session_id] = []
        self.active_connections[session_id].append(websocket)

    def disconnect(self, websocket: WebSocket, session_id: str):
        """Disconnect a WebSocket from a session."""
        if session_id in self.active_connections:
            if websocket in self.active_connections[session_id]:
                self.active_connections[session_id].remove(websocket)
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]

    async def broadcast(self, session_id: str, message: Dict[str, Any]):
        """Broadcast a message to all connections for a session."""
        if session_id in self.active_connections:
            dead_connections = []
            for connection in self.active_connections[session_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    dead_connections.append(connection)

            # Clean up dead connections
            for conn in dead_connections:
                self.disconnect(conn, session_id)


ws_manager = ConnectionManager()


@router.websocket("/{session_id}/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    WebSocket endpoint for real-time session updates.

    Receives:
    - {"type": "message", "content": "..."} - Send message to agent
    - {"type": "ping"} - Keep-alive ping

    Sends:
    - {"type": "agent_message", "content": "..."} - Agent response
    - {"type": "agent_started"} - Agent started
    - {"type": "agent_stopped"} - Agent stopped
    - {"type": "agent_error", "error": "..."} - Error occurred
    - {"type": "pong"} - Response to ping
    """
    await ws_manager.connect(websocket, session_id)

    manager = await get_agent_session_manager(db)

    # Create callback for agent events
    async def message_callback(event: Dict[str, Any]):
        await ws_manager.broadcast(session_id, event)

    try:
        # Get or create runner for this session
        runner = await manager.get_or_create_runner(
            session_id,
            message_callback=message_callback
        )

        # Send initial status
        await websocket.send_json({
            "type": "connected",
            "session_id": session_id,
            "is_running": runner.is_running,
        })

        # Handle incoming messages
        while True:
            try:
                data = await websocket.receive_json()
                msg_type = data.get("type")

                if msg_type == "ping":
                    await websocket.send_json({"type": "pong"})

                elif msg_type == "message":
                    content = data.get("content", "")
                    if content and runner.is_running:
                        await runner.send_message(content)
                    elif not runner.is_running:
                        await websocket.send_json({
                            "type": "error",
                            "message": "Agent is not running"
                        })

                elif msg_type == "start":
                    if not runner.is_running:
                        prompt = data.get("prompt", "")
                        session = await manager.get_session(session_id)
                        await runner.start(prompt or session.user_prompt)

                elif msg_type == "stop":
                    if runner.is_running:
                        await runner.stop()

                elif msg_type == "pause":
                    if runner.is_running:
                        await runner.pause()

                elif msg_type == "resume":
                    if runner.is_paused:
                        await runner.resume()

            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.exception(f"Error in WebSocket for session {session_id}")
                await websocket.send_json({
                    "type": "error",
                    "message": str(e)
                })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.exception(f"WebSocket error for session {session_id}")
    finally:
        ws_manager.disconnect(websocket, session_id)
