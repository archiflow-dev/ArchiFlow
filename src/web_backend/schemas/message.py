"""
Pydantic schemas for Message API.

Defines request/response models for message endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class MessageRoleEnum(str, Enum):
    """Message role values for API."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class MessageCreate(BaseModel):
    """Request schema for creating/sending a message."""

    content: str = Field(
        ...,
        min_length=1,
        description="Message content"
    )
    role: MessageRoleEnum = Field(
        default=MessageRoleEnum.USER,
        description="Role of the message sender"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "content": "Make the cat's expression more surprised in panel 2",
                    "role": "user",
                }
            ]
        }
    }


class MessageResponse(BaseModel):
    """Response schema for a single message."""

    id: str = Field(..., description="Unique message identifier")
    session_id: str = Field(..., description="Associated session ID")
    role: MessageRoleEnum = Field(..., description="Role of the message sender")
    content: str = Field(..., description="Message content")
    sequence: int = Field(..., description="Message sequence number in session")
    tool_name: Optional[str] = Field(None, description="Tool name if tool message")
    tool_call_id: Optional[str] = Field(None, description="Tool call ID if tool message")
    created_at: datetime = Field(..., description="Creation timestamp")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": "msg_xyz789abc123",
                    "session_id": "session_abc123def456",
                    "role": "assistant",
                    "content": "I've updated panel 2 with a more surprised expression.",
                    "sequence": 5,
                    "tool_name": None,
                    "tool_call_id": None,
                    "created_at": "2024-01-02T10:32:00Z",
                }
            ]
        }
    }


class MessageList(BaseModel):
    """Response schema for listing messages."""

    messages: List[MessageResponse] = Field(
        ...,
        description="List of messages"
    )
    total: int = Field(..., description="Total number of messages")
    session_id: str = Field(..., description="Session ID")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "messages": [],
                    "total": 0,
                    "session_id": "session_abc123def456",
                }
            ]
        }
    }
