"""
Pydantic schemas for Session API.

Defines request/response models for session endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class SessionStatusEnum(str, Enum):
    """Session status values for API."""
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    AWAITING_INPUT = "awaiting_input"
    COMPLETED = "completed"
    FAILED = "failed"


class SessionCreate(BaseModel):
    """Request schema for creating a new session."""

    agent_type: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Type of agent to run (e.g., 'comic', 'ppt', 'coding')"
    )
    user_prompt: str = Field(
        ...,
        min_length=1,
        description="Initial prompt/request for the agent"
    )
    project_directory: Optional[str] = Field(
        None,
        description="Optional working directory for the agent"
    )
    config: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional agent-specific configuration"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "agent_type": "comic",
                    "user_prompt": "Create a 4-panel comic about a cat learning to code",
                    "project_directory": None,
                }
            ]
        }
    }


class SessionUpdate(BaseModel):
    """Request schema for updating a session."""

    status: Optional[SessionStatusEnum] = Field(
        None,
        description="New status for the session"
    )
    workflow_state: Optional[Dict[str, Any]] = Field(
        None,
        description="Updated workflow state"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "status": "paused",
                }
            ]
        }
    }


class SessionResponse(BaseModel):
    """Response schema for a single session."""

    id: str = Field(..., description="Unique session identifier")
    agent_type: str = Field(..., description="Type of agent")
    user_prompt: str = Field(..., description="Initial user prompt")
    project_directory: Optional[str] = Field(None, description="Working directory")
    status: SessionStatusEnum = Field(..., description="Current session status")
    workflow_state: Optional[Dict[str, Any]] = Field(
        None,
        description="Current workflow state"
    )
    user_id: Optional[str] = Field(None, description="User ID")
    workspace_path: Optional[str] = Field(None, description="Workspace directory path")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": "session_abc123def456",
                    "agent_type": "comic",
                    "user_prompt": "Create a 4-panel comic about a cat learning to code",
                    "project_directory": None,
                    "status": "running",
                    "workflow_state": {"current_phase": "script_generation"},
                    "user_id": "default_user",
                    "workspace_path": "./data/workspaces/default_user/session_abc123def456",
                    "created_at": "2024-01-02T10:30:00Z",
                    "updated_at": "2024-01-02T10:31:00Z",
                }
            ]
        }
    }


class SessionList(BaseModel):
    """Response schema for listing sessions."""

    sessions: List[SessionResponse] = Field(
        ...,
        description="List of sessions"
    )
    total: int = Field(..., description="Total number of sessions matching query")
    page: int = Field(1, description="Current page number")
    page_size: int = Field(20, description="Number of items per page")
    has_more: bool = Field(False, description="Whether there are more results")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "sessions": [],
                    "total": 0,
                    "page": 1,
                    "page_size": 20,
                    "has_more": False,
                }
            ]
        }
    }
