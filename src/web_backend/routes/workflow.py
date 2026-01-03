"""
Workflow API routes.

Handles workflow state and phase management.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
import logging

from ..schemas.workflow import (
    WorkflowState,
    ApprovalRequest,
    ApprovalResponse,
    PhaseStatus,
    WorkflowPhase,
)
from ..services.workflow_controller import WorkflowController, get_workflow_definition
from ..services.session_store import get_session_store

router = APIRouter()
logger = logging.getLogger(__name__)

# Cache for workflow controllers (keyed by session_id)
_workflow_controllers: dict[str, WorkflowController] = {}


async def get_workflow_controller(session_id: str) -> WorkflowController:
    """
    Get or create a WorkflowController for a session.

    Note: In production, this would use proper dependency injection
    and get user_id from auth token.
    """
    if session_id not in _workflow_controllers:
        # Get session to determine agent type
        session_store = get_session_store()
        session = await session_store.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        _workflow_controllers[session_id] = WorkflowController(
            session_id=session_id,
            agent_type=session.agent_type,
            user_id="default_user",  # TODO: Get from auth
        )

    return _workflow_controllers[session_id]


def cleanup_workflow_controller(session_id: str):
    """Remove a workflow controller from cache (e.g., when session deleted)."""
    _workflow_controllers.pop(session_id, None)


@router.get("/", response_model=WorkflowState)
async def get_workflow_state(session_id: str):
    """
    Get the current workflow state for a session.

    Returns all phases and their current status.
    """
    controller = await get_workflow_controller(session_id)
    return await controller.get_current_state()


@router.post("/start", response_model=WorkflowState)
async def start_workflow(session_id: str):
    """
    Start the workflow by activating the first phase.

    This should be called after session creation to begin
    the workflow process.
    """
    controller = await get_workflow_controller(session_id)
    return await controller.start_workflow()


@router.post("/phases/{phase_id}/approve", response_model=ApprovalResponse)
async def approve_phase(
    session_id: str,
    phase_id: str,
    data: ApprovalRequest,
):
    """
    Approve or reject a workflow phase.

    If approved, the workflow proceeds to the next phase.
    If rejected, the agent will attempt to revise based on feedback.
    """
    controller = await get_workflow_controller(session_id)

    try:
        if data.approved:
            state = await controller.approve_phase(phase_id, data.feedback)
            next_phase = state.current_phase
            message = f"Phase '{phase_id}' approved"
            if next_phase:
                message += f", advancing to '{next_phase}'"
            else:
                message += ", workflow complete"

            return ApprovalResponse(
                phase_id=phase_id,
                status=PhaseStatus.APPROVED,
                next_phase=next_phase,
                message=message,
            )
        else:
            if not data.feedback:
                raise HTTPException(
                    status_code=400,
                    detail="Feedback is required when rejecting a phase"
                )
            state = await controller.reject_phase(phase_id, data.feedback)

            return ApprovalResponse(
                phase_id=phase_id,
                status=PhaseStatus.REJECTED,
                next_phase=None,
                message=f"Phase '{phase_id}' rejected. Agent will revise based on feedback.",
            )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/phases/{phase_id}/complete", response_model=WorkflowState)
async def complete_phase(
    session_id: str,
    phase_id: str,
):
    """
    Mark a phase as completed (for phases that don't require approval).

    This is typically called by the agent when it finishes a phase
    that has requires_approval=False.
    """
    controller = await get_workflow_controller(session_id)

    try:
        return await controller.complete_phase(phase_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/phases/{phase_id}/awaiting-approval", response_model=WorkflowState)
async def set_phase_awaiting_approval(
    session_id: str,
    phase_id: str,
):
    """
    Set a phase to awaiting approval status.

    This is called by the agent when it has completed work on a phase
    that requires user approval before proceeding.
    """
    controller = await get_workflow_controller(session_id)

    try:
        return await controller.set_phase_awaiting_approval(phase_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/phases/{phase_id}", response_model=WorkflowPhase)
async def get_phase_details(
    session_id: str,
    phase_id: str,
):
    """
    Get detailed information about a specific phase.
    """
    controller = await get_workflow_controller(session_id)

    # Find the phase
    for phase in controller.phases:
        if phase.id == phase_id:
            return phase

    raise HTTPException(status_code=404, detail=f"Phase '{phase_id}' not found")


@router.post("/reset", response_model=WorkflowState)
async def reset_workflow(session_id: str):
    """
    Reset the workflow to its initial state.

    All phases will be set to PENDING and the current phase cleared.
    Use with caution - this loses all workflow progress.
    """
    controller = await get_workflow_controller(session_id)
    return await controller.reset_workflow()
