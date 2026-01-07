"""
Comment models for ArchiFlow Web Backend.

Provides Pydantic models for document comments with file-based storage.
Comments are stored in .comments.json files within session workspaces.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum
import uuid


class CommentStatus(str, Enum):
    """Status of a comment."""
    PENDING = "pending"       # Comment created, not yet addressed
    RESOLVED = "resolved"     # Comment marked as resolved by user
    APPLIED = "applied"       # Comment was applied by agent
    SUBMITTED = "submitted"   # Comment submitted to agent, awaiting completion


class Comment(BaseModel):
    """
    A comment on a document.

    Comments are attached to specific lines in a file and can include
    selected text context. They can be submitted to agents for document updates.
    """
    id: str = Field(default_factory=lambda: f"comment_{uuid.uuid4().hex[:12]}")
    session_id: str = Field(..., description="Session this comment belongs to")
    file_path: str = Field(..., description="Path to the file being commented on (relative to workspace)")
    line_number: int = Field(..., ge=1, description="Line number where comment is placed")
    end_line_number: Optional[int] = Field(None, ge=1, description="End line number for multi-line/range comments")
    selected_text: str = Field(default="", description="Text snippet being commented on")
    comment_text: str = Field(..., min_length=1, description="User's comment content")
    author: str = Field(default="default_user", description="User who created the comment")
    status: CommentStatus = Field(default=CommentStatus.PENDING, description="Current status of the comment")
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

    class Config:
        json_schema_extra = {
            "example": {
                "id": "comment_a1b2c3d4e5f6",
                "session_id": "session_123456789abc",
                "file_path": "docs/chapter1.md",
                "line_number": 23,
                "end_line_number": 25,
                "selected_text": "The quick brown fox",
                "comment_text": "This should be more descriptive",
                "author": "default_user",
                "status": "pending",
                "created_at": "2026-01-06T10:30:00",
                "updated_at": "2026-01-06T10:30:00"
            }
        }


class CommentCreate(BaseModel):
    """Request model for creating a comment."""
    file_path: str = Field(..., description="Path to the file being commented on")
    line_number: int = Field(..., ge=1, description="Line number where comment is placed")
    end_line_number: Optional[int] = Field(None, ge=1, description="End line number for multi-line/range comments")
    selected_text: str = Field(default="", description="Text snippet being commented on")
    comment_text: str = Field(..., min_length=1, description="User's comment content")
    author: str = Field(default="default_user", description="User who created the comment")


class CommentUpdate(BaseModel):
    """Request model for updating a comment."""
    comment_text: Optional[str] = Field(None, min_length=1, description="Updated comment content")
    status: Optional[CommentStatus] = Field(None, description="Updated status")


class CommentListResponse(BaseModel):
    """Response model for listing comments."""
    comments: List[Comment]
    total_count: int
    file_path: Optional[str] = None  # If filtered by file


class CommentSubmissionRequest(BaseModel):
    """Request model for submitting comments to agent."""
    file_path: Optional[str] = Field(None, description="Submit only comments for this file (null = all pending)")
    prompt_override: Optional[str] = Field(None, description="Custom prompt to send to agent (null = auto-generate)")


class CommentSubmissionResponse(BaseModel):
    """Response model for comment submission."""
    submitted_count: int
    comment_ids: List[str]
    message: str
