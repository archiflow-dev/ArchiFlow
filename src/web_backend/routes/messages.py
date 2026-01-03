"""
Message API routes.

Handles chat message operations for sessions.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List

from ..database.connection import get_db
from ..schemas.message import MessageCreate, MessageResponse, MessageList
from ..models.message import Message, MessageRole

router = APIRouter()


@router.get("/", response_model=MessageList)
async def list_messages(
    session_id: str,
    limit: int = Query(100, ge=1, le=1000, description="Max messages to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_db),
):
    """
    List messages in a session.

    Returns messages ordered by sequence number.
    """
    # Get total count
    count_result = await db.execute(
        select(func.count())
        .select_from(Message)
        .where(Message.session_id == session_id)
    )
    total = count_result.scalar() or 0

    # Get messages
    result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.sequence.asc())
        .offset(offset)
        .limit(limit)
    )
    messages = list(result.scalars().all())

    return MessageList(
        messages=[MessageResponse.model_validate(m.to_dict()) for m in messages],
        total=total,
        session_id=session_id,
    )


@router.post("/", response_model=MessageResponse, status_code=201)
async def send_message(
    session_id: str,
    data: MessageCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Send a message to a session.

    This adds a new message and triggers agent processing.
    """
    # Get next sequence number
    max_seq_result = await db.execute(
        select(func.max(Message.sequence))
        .where(Message.session_id == session_id)
    )
    max_seq = max_seq_result.scalar() or 0

    # Create message
    message = Message(
        session_id=session_id,
        role=MessageRole(data.role.value),
        content=data.content,
        sequence=max_seq + 1,
    )

    db.add(message)
    await db.commit()
    await db.refresh(message)

    # TODO: Trigger agent processing via WebSocket in Phase 2

    return MessageResponse.model_validate(message.to_dict())


@router.get("/{message_id}", response_model=MessageResponse)
async def get_message(
    session_id: str,
    message_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a specific message by ID.
    """
    result = await db.execute(
        select(Message)
        .where(Message.id == message_id)
        .where(Message.session_id == session_id)
    )
    message = result.scalar_one_or_none()

    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    return MessageResponse.model_validate(message.to_dict())
