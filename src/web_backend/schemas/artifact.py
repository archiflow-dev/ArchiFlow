"""
Pydantic schemas for Artifact API.

Defines request/response models for artifact endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ArtifactInfo(BaseModel):
    """Information about a single artifact."""

    name: str = Field(..., description="File name")
    path: str = Field(..., description="Relative path within workspace")
    is_directory: bool = Field(..., description="Whether this is a directory")
    size: Optional[int] = Field(None, description="File size in bytes (None for directories)")
    mime_type: Optional[str] = Field(None, description="MIME type of file")
    modified_at: datetime = Field(..., description="Last modification timestamp")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "script.md",
                    "path": "artifacts/script.md",
                    "is_directory": False,
                    "size": 2048,
                    "mime_type": "text/markdown",
                    "modified_at": "2024-01-02T10:30:00Z",
                }
            ]
        }
    }


class ArtifactContent(BaseModel):
    """Response schema for artifact content."""

    path: str = Field(..., description="Artifact path")
    content: Optional[str] = Field(
        None,
        description="Text content (for text files)"
    )
    content_base64: Optional[str] = Field(
        None,
        description="Base64-encoded content (for binary files)"
    )
    mime_type: str = Field(..., description="MIME type")
    size: int = Field(..., description="File size in bytes")
    is_binary: bool = Field(..., description="Whether content is binary")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "path": "artifacts/script.md",
                    "content": "# Scene 1\n\nPANEL 1:\n...",
                    "content_base64": None,
                    "mime_type": "text/markdown",
                    "size": 2048,
                    "is_binary": False,
                }
            ]
        }
    }


class ArtifactList(BaseModel):
    """Response schema for listing artifacts."""

    artifacts: List[ArtifactInfo] = Field(
        ...,
        description="List of artifacts"
    )
    path: str = Field(..., description="Current directory path")
    total: int = Field(..., description="Total number of items")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "artifacts": [],
                    "path": "artifacts/",
                    "total": 0,
                }
            ]
        }
    }


class ArtifactCreate(BaseModel):
    """Request schema for creating/uploading an artifact."""

    path: str = Field(
        ...,
        min_length=1,
        description="Target path within workspace"
    )
    content: Optional[str] = Field(
        None,
        description="Text content"
    )
    content_base64: Optional[str] = Field(
        None,
        description="Base64-encoded content for binary files"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "path": "artifacts/notes.md",
                    "content": "# My Notes\n\nSome content here...",
                    "content_base64": None,
                }
            ]
        }
    }
