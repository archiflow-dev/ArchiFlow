"""
Comments API routes.

Handles document comment CRUD operations and agent submission.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..database.connection import get_db
from ..models.comment import (
    Comment,
    CommentCreate,
    CommentUpdate,
    CommentListResponse,
    CommentStatus,
    CommentSubmissionRequest,
    CommentSubmissionResponse,
)
from ..services.comment_service import (
    CommentService,
    CommentNotFoundError,
    CommentServiceError,
    get_comment_service,
)
from ..services.agent_session_manager import AgentSessionManager, get_agent_session_manager
from ..services.agent_runner import AgentExecutionError

logger = logging.getLogger(__name__)


# Local dependency wrapper to avoid circular imports
async def get_manager(
    db: AsyncSession = Depends(get_db)
) -> AgentSessionManager:
    """Get AgentSessionManager dependency."""
    return await get_agent_session_manager(db)

router = APIRouter()


def get_comment_service_dependency() -> CommentService:
    """Dependency to get comment service."""
    return get_comment_service()


# ============================================================================
# List Comments
# ============================================================================

@router.get(
    "/sessions/{session_id}/comments",
    response_model=CommentListResponse,
    summary="List all comments for a session"
)
async def list_comments(
    session_id: str,
    file_path: Optional[str] = Query(None, description="Filter by file path"),
    status: Optional[CommentStatus] = Query(None, description="Filter by status"),
    service: CommentService = Depends(get_comment_service_dependency),
) -> CommentListResponse:
    """
    List all comments for a session.

    Args:
        session_id: Session ID
        file_path: Optional filter by file path
        status: Optional filter by status (pending, resolved, applied, submitted)

    Returns:
        List of comments matching the filters
    """
    try:
        comments = service.list_comments(
            session_id=session_id,
            file_path=file_path,
            status=status,
        )

        return CommentListResponse(
            comments=comments,
            total_count=len(comments),
            file_path=file_path,
        )

    except CommentServiceError as e:
        logger.error(f"Error listing comments for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/sessions/{session_id}/files/{file_path:path}/comments",
    response_model=CommentListResponse,
    summary="List comments for a specific file"
)
async def list_file_comments(
    session_id: str,
    file_path: str,  # :path type allows slashes in the value
    status: Optional[CommentStatus] = Query(None, description="Filter by status"),
    service: CommentService = Depends(get_comment_service_dependency),
) -> CommentListResponse:
    """
    List all comments for a specific file in a session.

    Args:
        session_id: Session ID
        file_path: Path to the file within the workspace
        status: Optional filter by status

    Returns:
        List of comments for the file
    """
    try:
        comments = service.list_comments(
            session_id=session_id,
            file_path=file_path,
            status=status,
        )

        return CommentListResponse(
            comments=comments,
            total_count=len(comments),
            file_path=file_path,
        )

    except CommentServiceError as e:
        logger.error(f"Error listing comments for {file_path} in session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Get Single Comment
# ============================================================================

@router.get(
    "/comments/{comment_id}",
    response_model=Comment,
    summary="Get a specific comment"
)
async def get_comment(
    comment_id: str,
    session_id: str = Query(..., description="Session ID"),
    service: CommentService = Depends(get_comment_service_dependency),
) -> Comment:
    """
    Get a specific comment by ID.

    Args:
        comment_id: Comment ID
        session_id: Session ID

    Returns:
        The comment

    Raises:
        404: If comment not found
    """
    try:
        return service.get_comment(
            comment_id=comment_id,
            session_id=session_id,
        )
    except CommentNotFoundError:
        raise HTTPException(status_code=404, detail=f"Comment {comment_id} not found")
    except CommentServiceError as e:
        logger.error(f"Error getting comment {comment_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Create Comment
# ============================================================================

@router.post(
    "/sessions/{session_id}/comments",
    response_model=Comment,
    status_code=201,
    summary="Create a new comment"
)
async def create_comment(
    session_id: str,
    comment_data: CommentCreate,
    service: CommentService = Depends(get_comment_service_dependency),
) -> Comment:
    """
    Create a new comment on a document.

    Args:
        session_id: Session ID
        comment_data: Comment creation data

    Returns:
        The created comment
    """
    try:
        comment = service.create_comment(
            comment_create=comment_data,
            session_id=session_id,
        )

        logger.info(
            f"Created comment {comment.id} on {comment.file_path}:{comment.line_number}"
        )

        return comment

    except CommentServiceError as e:
        logger.error(f"Error creating comment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Update Comment
# ============================================================================

@router.put(
    "/comments/{comment_id}",
    response_model=Comment,
    summary="Update a comment"
)
async def update_comment(
    comment_id: str,
    comment_update: CommentUpdate,
    session_id: str = Query(..., description="Session ID"),
    service: CommentService = Depends(get_comment_service_dependency),
) -> Comment:
    """
    Update an existing comment.

    Args:
        comment_id: Comment ID
        comment_update: Update data (comment_text and/or status)
        session_id: Session ID

    Returns:
        The updated comment

    Raises:
        404: If comment not found
    """
    try:
        comment = service.update_comment(
            comment_id=comment_id,
            comment_update=comment_update,
            session_id=session_id,
        )

        logger.info(f"Updated comment {comment_id}")
        return comment

    except CommentNotFoundError:
        raise HTTPException(status_code=404, detail=f"Comment {comment_id} not found")
    except CommentServiceError as e:
        logger.error(f"Error updating comment {comment_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Resolve Comment
# ============================================================================

@router.post(
    "/comments/{comment_id}/resolve",
    response_model=Comment,
    summary="Mark a comment as resolved"
)
async def resolve_comment(
    comment_id: str,
    session_id: str = Query(..., description="Session ID"),
    service: CommentService = Depends(get_comment_service_dependency),
) -> Comment:
    """
    Mark a comment as resolved (user manually addressed it).

    Args:
        comment_id: Comment ID
        session_id: Session ID

    Returns:
        The updated comment

    Raises:
        404: If comment not found
    """
    try:
        update = CommentUpdate(status=CommentStatus.RESOLVED)
        comment = service.update_comment(
            comment_id=comment_id,
            comment_update=update,
            session_id=session_id,
        )

        logger.info(f"Resolved comment {comment_id}")
        return comment

    except CommentNotFoundError:
        raise HTTPException(status_code=404, detail=f"Comment {comment_id} not found")
    except CommentServiceError as e:
        logger.error(f"Error resolving comment {comment_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Delete Comment
# ============================================================================

@router.delete(
    "/comments/{comment_id}",
    status_code=204,
    summary="Delete a comment"
)
async def delete_comment(
    comment_id: str,
    session_id: str = Query(..., description="Session ID"),
    service: CommentService = Depends(get_comment_service_dependency),
) -> None:
    """
    Delete a comment.

    Args:
        comment_id: Comment ID
        session_id: Session ID

    Raises:
        404: If comment not found
    """
    try:
        service.delete_comment(
            comment_id=comment_id,
            session_id=session_id,
        )

        logger.info(f"Deleted comment {comment_id}")

    except CommentNotFoundError:
        raise HTTPException(status_code=404, detail=f"Comment {comment_id} not found")
    except CommentServiceError as e:
        logger.error(f"Error deleting comment {comment_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Submit Comments to Agent
# ============================================================================

@router.post(
    "/sessions/{session_id}/comments/submit-to-agent",
    response_model=CommentSubmissionResponse,
    summary="Submit pending comments to the agent"
)
async def submit_comments_to_agent(
    session_id: str,
    request: CommentSubmissionRequest,
    service: CommentService = Depends(get_comment_service_dependency),
    manager: AgentSessionManager = Depends(get_manager),
) -> CommentSubmissionResponse:
    """
    Submit pending comments to the agent for document updates.

    This formats all pending comments (or comments for a specific file)
    and sends them to the agent. Comments are marked as 'submitted'.

    Args:
        session_id: Session ID
        request: Submission options (file_path filter, prompt_override)
        manager: Agent session manager for sending messages to agent

    Returns:
        Submission response with count and message

    Raises:
        400: If session is not active
        404: If session not found
        500: For other errors
    """
    try:
        # Get pending comments
        comments = service.get_pending_comments(
            session_id=session_id,
            file_path=request.file_path,
        )

        if not comments:
            return CommentSubmissionResponse(
                submitted_count=0,
                comment_ids=[],
                message="No pending comments to submit."
            )

        # Format comments for agent
        formatted_comments = service.format_comments_for_agent(
            comments=comments,
            file_path=request.file_path,
        )

        # Log detailed submission info
        logger.info(f"Submitting {len(comments)} comments to agent for session {session_id}")
        logger.info(f"Formatted comments:\n{formatted_comments}")
        logger.info(f"Comment details:")
        for comment in comments:
            logger.info(f"  - {comment.file_path}:{comment.line_number} ({comment.id})")
            logger.info(f"    Text: {comment.selected_text or '(no text selected)'}")
            logger.info(f"    Comment: {comment.comment_text}")
            logger.info(f"    Status: {comment.status}")

        # Build the prompt to send to agent
        if request.prompt_override:
            prompt = request.prompt_override
        else:
            # Add context header to the formatted comments
            prompt = formatted_comments

        # Send to the agent via session manager
        try:
            await manager.send_message(session_id, prompt)
            logger.info(f"Successfully sent {len(comments)} comments to agent for session {session_id}")
        except AgentExecutionError as e:
            # Agent not running or session not active
            logger.warning(f"Cannot send to agent: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Cannot send comments to agent: {str(e)}. "
                       f"Please ensure the agent is running."
            )

        # Mark comments as submitted
        comment_ids = [c.id for c in comments]
        marked_count = service.mark_comments_submitted(
            comment_ids=comment_ids,
            session_id=session_id,
        )

        plural = "s" if marked_count != 1 else ""
        message = f"Submitted {marked_count} comment{plural} to agent."

        return CommentSubmissionResponse(
            submitted_count=marked_count,
            comment_ids=comment_ids,
            message=message,
        )

    except HTTPException:
        raise
    except CommentServiceError as e:
        logger.error(f"Error submitting comments for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Get Pending Comments
# ============================================================================

@router.get(
    "/sessions/{session_id}/comments/pending",
    response_model=CommentListResponse,
    summary="Get pending comments for submission"
)
async def get_pending_comments(
    session_id: str,
    file_path: Optional[str] = Query(None, description="Filter by file path"),
    service: CommentService = Depends(get_comment_service_dependency),
) -> CommentListResponse:
    """
    Get all pending comments that can be submitted to the agent.

    Args:
        session_id: Session ID
        file_path: Optional filter by file path

    Returns:
        List of pending comments
    """
    try:
        comments = service.get_pending_comments(
            session_id=session_id,
            file_path=file_path,
        )

        return CommentListResponse(
            comments=comments,
            total_count=len(comments),
        )

    except CommentServiceError as e:
        logger.error(f"Error getting pending comments for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
