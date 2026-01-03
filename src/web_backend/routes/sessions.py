"""
Session API routes.

Handles session CRUD operations.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from ..database.connection import get_db
from ..schemas.session import (
    SessionCreate,
    SessionResponse,
    SessionUpdate,
    SessionList,
    SessionStatusEnum,
)
from ..services.session_service import SessionService
from ..models.session import SessionStatus

router = APIRouter()


def get_session_service(db: AsyncSession = Depends(get_db)) -> SessionService:
    """Dependency to get session service."""
    return SessionService(db)


@router.post("/", response_model=SessionResponse, status_code=201)
async def create_session(
    data: SessionCreate,
    service: SessionService = Depends(get_session_service),
):
    """
    Create a new agent session.

    This creates a new session with the specified agent type and initial prompt.
    The session will be in 'created' status until the agent is started.
    """
    session = await service.create(
        agent_type=data.agent_type,
        user_prompt=data.user_prompt,
        project_directory=data.project_directory,
    )
    return SessionResponse.model_validate(session.to_dict())


@router.get("/", response_model=SessionList)
async def list_sessions(
    status: Optional[SessionStatusEnum] = Query(None, description="Filter by status"),
    agent_type: Optional[str] = Query(None, description="Filter by agent type"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    service: SessionService = Depends(get_session_service),
):
    """
    List all sessions with optional filtering.

    Supports pagination and filtering by status and agent type.
    """
    # Convert enum to model enum if provided
    model_status = SessionStatus(status.value) if status else None

    sessions, total = await service.list(
        status=model_status,
        agent_type=agent_type,
        page=page,
        page_size=page_size,
    )

    return SessionList(
        sessions=[SessionResponse.model_validate(s.to_dict()) for s in sessions],
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total,
    )


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    service: SessionService = Depends(get_session_service),
):
    """
    Get a specific session by ID.

    Returns the session details including current status and workflow state.
    """
    session = await service.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionResponse.model_validate(session.to_dict())


@router.patch("/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: str,
    data: SessionUpdate,
    service: SessionService = Depends(get_session_service),
):
    """
    Update a session.

    Can update status and workflow state.
    """
    session = await service.update(session_id, data)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionResponse.model_validate(session.to_dict())


@router.delete("/{session_id}", status_code=204)
async def delete_session(
    session_id: str,
    service: SessionService = Depends(get_session_service),
):
    """
    Delete a session.

    This will also delete all associated messages and artifacts.
    """
    deleted = await service.delete(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")

    return None


@router.post("/{session_id}/start", response_model=SessionResponse)
async def start_session(
    session_id: str,
    service: SessionService = Depends(get_session_service),
):
    """
    Start a session's agent.

    Changes the session status to 'running' and begins agent execution.
    """
    session = await service.update_status(session_id, SessionStatus.RUNNING)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # TODO: Actually start the agent in background
    # This will be implemented in Phase 2

    return SessionResponse.model_validate(session.to_dict())


@router.post("/{session_id}/pause", response_model=SessionResponse)
async def pause_session(
    session_id: str,
    service: SessionService = Depends(get_session_service),
):
    """
    Pause a running session.

    The agent will stop processing but can be resumed later.
    """
    session = await service.update_status(session_id, SessionStatus.PAUSED)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionResponse.model_validate(session.to_dict())


@router.post("/{session_id}/resume", response_model=SessionResponse)
async def resume_session(
    session_id: str,
    service: SessionService = Depends(get_session_service),
):
    """
    Resume a paused session.

    The agent will continue processing from where it left off.
    """
    session = await service.update_status(session_id, SessionStatus.RUNNING)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionResponse.model_validate(session.to_dict())
