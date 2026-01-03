"""
Pydantic schemas for Workflow API.

Defines request/response models for workflow endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class PhaseStatus(str, Enum):
    """Status of a workflow phase."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"
    SKIPPED = "skipped"


class WorkflowPhase(BaseModel):
    """Information about a single workflow phase."""

    id: str = Field(..., description="Phase identifier")
    name: str = Field(..., description="Human-readable phase name")
    description: Optional[str] = Field(None, description="Phase description")
    status: PhaseStatus = Field(..., description="Current phase status")
    order: int = Field(..., description="Phase order in workflow")
    artifacts: List[str] = Field(
        default_factory=list,
        description="Artifacts produced by this phase"
    )
    started_at: Optional[datetime] = Field(None, description="When phase started")
    completed_at: Optional[datetime] = Field(None, description="When phase completed")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "script_generation",
                    "name": "Script Generation",
                    "description": "Generate the comic script from user prompt",
                    "status": "completed",
                    "order": 1,
                    "artifacts": ["artifacts/script.md"],
                    "started_at": "2024-01-02T10:30:00Z",
                    "completed_at": "2024-01-02T10:31:00Z",
                }
            ]
        }
    }


class WorkflowState(BaseModel):
    """Complete workflow state for a session."""

    session_id: str = Field(..., description="Associated session ID")
    agent_type: str = Field(..., description="Agent type")
    current_phase: Optional[str] = Field(None, description="Current phase ID")
    phases: List[WorkflowPhase] = Field(
        default_factory=list,
        description="All workflow phases"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Agent-specific metadata"
    )
    progress_percent: float = Field(
        0.0,
        ge=0.0,
        le=100.0,
        description="Overall progress percentage"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "session_id": "session_abc123def456",
                    "agent_type": "comic",
                    "current_phase": "visual_specification",
                    "phases": [],
                    "metadata": {},
                    "progress_percent": 25.0,
                }
            ]
        }
    }


class ApprovalRequest(BaseModel):
    """Request schema for phase approval."""

    approved: bool = Field(
        ...,
        description="Whether the phase is approved"
    )
    feedback: Optional[str] = Field(
        None,
        description="Optional feedback or revision instructions"
    )
    revisions: Optional[Dict[str, Any]] = Field(
        None,
        description="Specific revision requests"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "approved": True,
                    "feedback": None,
                    "revisions": None,
                },
                {
                    "approved": False,
                    "feedback": "Please make the dialogue more dramatic",
                    "revisions": {"lines": [5, 10, 15]},
                }
            ]
        }
    }


class ApprovalResponse(BaseModel):
    """Response schema for phase approval."""

    phase_id: str = Field(..., description="Phase that was approved/rejected")
    status: PhaseStatus = Field(..., description="New phase status")
    next_phase: Optional[str] = Field(None, description="Next phase ID if approved")
    message: str = Field(..., description="Status message")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "phase_id": "script_generation",
                    "status": "approved",
                    "next_phase": "visual_specification",
                    "message": "Phase approved. Proceeding to visual specification.",
                }
            ]
        }
    }
