"""
Workflow Controller for ArchiFlow Web Backend.

Manages workflow state and phase transitions for agent sessions.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import logging
import json

from ..schemas.workflow import WorkflowState, WorkflowPhase, PhaseStatus
from .workspace_manager import get_workspace_manager

logger = logging.getLogger(__name__)


# Workflow definitions for different agent types
WORKFLOW_DEFINITIONS: Dict[str, List[dict]] = {
    "comic": [
        {
            "id": "script_generation",
            "name": "Script Generation",
            "description": "Generate the comic script from user prompt",
            "order": 1,
            "requires_approval": True,
            "artifacts": ["artifacts/script.md"],
        },
        {
            "id": "visual_specification",
            "name": "Visual Specification",
            "description": "Create detailed visual specifications for panels",
            "order": 2,
            "requires_approval": True,
            "artifacts": ["artifacts/comic_spec.md"],
        },
        {
            "id": "character_references",
            "name": "Character References",
            "description": "Generate character reference images",
            "order": 3,
            "requires_approval": True,
            "artifacts": ["artifacts/character_refs/"],
        },
        {
            "id": "panel_generation",
            "name": "Panel Generation",
            "description": "Generate comic panels",
            "order": 4,
            "requires_approval": True,
            "artifacts": ["artifacts/panels/"],
        },
        {
            "id": "export",
            "name": "Export",
            "description": "Export final comic to PDF",
            "order": 5,
            "requires_approval": False,
            "artifacts": ["exports/comic.pdf"],
        },
    ],
    "ppt": [
        {
            "id": "outline",
            "name": "Outline",
            "description": "Create presentation outline",
            "order": 1,
            "requires_approval": True,
            "artifacts": ["artifacts/outline.json"],
        },
        {
            "id": "slide_design",
            "name": "Slide Design",
            "description": "Design individual slides",
            "order": 2,
            "requires_approval": True,
            "artifacts": ["artifacts/slide_descriptions.json"],
        },
        {
            "id": "visual_generation",
            "name": "Visual Generation",
            "description": "Generate slide visuals",
            "order": 3,
            "requires_approval": True,
            "artifacts": ["artifacts/slides/"],
        },
        {
            "id": "export",
            "name": "Export",
            "description": "Export to PPTX",
            "order": 4,
            "requires_approval": False,
            "artifacts": ["exports/presentation.pptx"],
        },
    ],
    "coding": [
        {
            "id": "planning",
            "name": "Planning",
            "description": "Analyze task and create implementation plan",
            "order": 1,
            "requires_approval": False,
            "artifacts": [],
        },
        {
            "id": "implementation",
            "name": "Implementation",
            "description": "Write and modify code",
            "order": 2,
            "requires_approval": False,
            "artifacts": [],
        },
        {
            "id": "verification",
            "name": "Verification",
            "description": "Run tests and verify changes",
            "order": 3,
            "requires_approval": False,
            "artifacts": [],
        },
    ],
    "research": [
        {
            "id": "research",
            "name": "Research",
            "description": "Gather information from various sources",
            "order": 1,
            "requires_approval": False,
            "artifacts": [],
        },
        {
            "id": "synthesis",
            "name": "Synthesis",
            "description": "Synthesize findings into a report",
            "order": 2,
            "requires_approval": False,
            "artifacts": ["artifacts/report.md"],
        },
    ],
}


def get_workflow_type(agent_type: str) -> str:
    """Get workflow type for an agent."""
    phase_heavy = {"comic", "ppt"}
    return "phase_heavy" if agent_type in phase_heavy else "chat_heavy"


class WorkflowController:
    """
    Controls workflow state and phase transitions for a session.

    Manages:
    - Phase status tracking
    - Phase transitions (approval/rejection)
    - Progress calculation
    - State persistence
    """

    def __init__(
        self,
        session_id: str,
        agent_type: str,
        user_id: str = "default_user"
    ):
        """
        Initialize WorkflowController.

        Args:
            session_id: Session ID
            agent_type: Agent type (e.g., 'comic', 'ppt')
            user_id: User ID
        """
        self.session_id = session_id
        self.agent_type = agent_type
        self.user_id = user_id
        self.workspace_manager = get_workspace_manager()

        # Load phases for this agent type
        self.phases = self._load_phases()
        self.current_phase_id: Optional[str] = None

        # Try to load persisted state
        self._load_state()

    def _load_phases(self) -> List[WorkflowPhase]:
        """Load phase definitions for agent type."""
        definitions = WORKFLOW_DEFINITIONS.get(self.agent_type, [])

        phases = []
        for defn in definitions:
            phase = WorkflowPhase(
                id=defn["id"],
                name=defn["name"],
                description=defn.get("description"),
                status=PhaseStatus.PENDING,
                order=defn["order"],
                artifacts=defn.get("artifacts", []),
                started_at=None,
                completed_at=None,
            )
            phases.append(phase)

        return phases

    def _get_state_file_path(self):
        """Get path to state file."""
        workspace = self.workspace_manager.get_workspace_path(
            self.user_id, self.session_id
        )
        return workspace / ".archiflow" / "workflow.json"

    def _load_state(self):
        """Load persisted workflow state."""
        state_file = self._get_state_file_path()

        if state_file.exists():
            try:
                with open(state_file, 'r') as f:
                    state = json.load(f)

                self.current_phase_id = state.get("current_phase")

                # Update phase statuses from persisted state
                for phase_state in state.get("phases", []):
                    for phase in self.phases:
                        if phase.id == phase_state["id"]:
                            phase.status = PhaseStatus(phase_state["status"])
                            phase.started_at = phase_state.get("started_at")
                            phase.completed_at = phase_state.get("completed_at")

                logger.info(f"Loaded workflow state for session {self.session_id}")
            except Exception as e:
                logger.warning(f"Failed to load workflow state: {e}")

    def _save_state(self):
        """Persist workflow state."""
        state_file = self._get_state_file_path()

        # Ensure directory exists
        state_file.parent.mkdir(parents=True, exist_ok=True)

        state = {
            "session_id": self.session_id,
            "agent_type": self.agent_type,
            "current_phase": self.current_phase_id,
            "phases": [
                {
                    "id": p.id,
                    "status": p.status.value,
                    "started_at": p.started_at,
                    "completed_at": p.completed_at,
                }
                for p in self.phases
            ],
            "updated_at": datetime.utcnow().isoformat(),
        }

        with open(state_file, 'w') as f:
            json.dump(state, f, indent=2)

    def _get_phase(self, phase_id: str) -> Optional[WorkflowPhase]:
        """Get phase by ID."""
        for phase in self.phases:
            if phase.id == phase_id:
                return phase
        return None

    def _get_next_phase(self, current_phase_id: str) -> Optional[WorkflowPhase]:
        """Get the next phase after the given one."""
        current = self._get_phase(current_phase_id)
        if not current:
            return None

        for phase in self.phases:
            if phase.order == current.order + 1:
                return phase
        return None

    def _calculate_progress(self) -> float:
        """Calculate overall progress percentage."""
        if not self.phases:
            return 0.0

        completed = sum(
            1 for p in self.phases
            if p.status in (PhaseStatus.APPROVED, PhaseStatus.COMPLETED)
        )
        return (completed / len(self.phases)) * 100

    async def get_current_state(self) -> WorkflowState:
        """Get current workflow state."""
        return WorkflowState(
            session_id=self.session_id,
            agent_type=self.agent_type,
            current_phase=self.current_phase_id,
            phases=self.phases,
            metadata={
                "workflow_type": get_workflow_type(self.agent_type),
            },
            progress_percent=self._calculate_progress(),
        )

    async def start_workflow(self) -> WorkflowState:
        """Start the workflow by activating the first phase."""
        if self.phases:
            first_phase = self.phases[0]
            first_phase.status = PhaseStatus.IN_PROGRESS
            first_phase.started_at = datetime.utcnow().isoformat()
            self.current_phase_id = first_phase.id
            self._save_state()

        return await self.get_current_state()

    async def set_phase_awaiting_approval(self, phase_id: str) -> WorkflowState:
        """Set a phase to awaiting approval status."""
        phase = self._get_phase(phase_id)
        if not phase:
            raise ValueError(f"Phase {phase_id} not found")

        phase.status = PhaseStatus.AWAITING_APPROVAL
        self._save_state()

        return await self.get_current_state()

    async def approve_phase(
        self,
        phase_id: str,
        feedback: Optional[str] = None
    ) -> WorkflowState:
        """
        Approve a phase and advance to the next.

        Args:
            phase_id: Phase ID to approve
            feedback: Optional feedback/notes

        Returns:
            Updated workflow state
        """
        phase = self._get_phase(phase_id)
        if not phase:
            raise ValueError(f"Phase {phase_id} not found")

        # Update phase status
        phase.status = PhaseStatus.APPROVED
        phase.completed_at = datetime.utcnow().isoformat()

        # Advance to next phase
        next_phase = self._get_next_phase(phase_id)
        if next_phase:
            next_phase.status = PhaseStatus.IN_PROGRESS
            next_phase.started_at = datetime.utcnow().isoformat()
            self.current_phase_id = next_phase.id
        else:
            self.current_phase_id = None

        self._save_state()

        logger.info(f"Approved phase {phase_id} for session {self.session_id}")
        return await self.get_current_state()

    async def reject_phase(
        self,
        phase_id: str,
        feedback: str
    ) -> WorkflowState:
        """
        Reject a phase with feedback for revision.

        Args:
            phase_id: Phase ID to reject
            feedback: Required feedback for revision

        Returns:
            Updated workflow state
        """
        phase = self._get_phase(phase_id)
        if not phase:
            raise ValueError(f"Phase {phase_id} not found")

        # Update phase status
        phase.status = PhaseStatus.REJECTED
        # Keep phase as current - agent will revise

        self._save_state()

        logger.info(f"Rejected phase {phase_id} for session {self.session_id}")
        return await self.get_current_state()

    async def complete_phase(self, phase_id: str) -> WorkflowState:
        """
        Mark a phase as completed (for phases that don't require approval).

        Args:
            phase_id: Phase ID to complete

        Returns:
            Updated workflow state
        """
        phase = self._get_phase(phase_id)
        if not phase:
            raise ValueError(f"Phase {phase_id} not found")

        phase.status = PhaseStatus.COMPLETED
        phase.completed_at = datetime.utcnow().isoformat()

        # Advance to next phase
        next_phase = self._get_next_phase(phase_id)
        if next_phase:
            next_phase.status = PhaseStatus.IN_PROGRESS
            next_phase.started_at = datetime.utcnow().isoformat()
            self.current_phase_id = next_phase.id
        else:
            self.current_phase_id = None

        self._save_state()

        return await self.get_current_state()

    async def reset_workflow(self) -> WorkflowState:
        """Reset workflow to initial state."""
        for phase in self.phases:
            phase.status = PhaseStatus.PENDING
            phase.started_at = None
            phase.completed_at = None

        self.current_phase_id = None
        self._save_state()

        return await self.get_current_state()


def get_workflow_definition(agent_type: str) -> Optional[dict]:
    """
    Get workflow definition for an agent type.

    Args:
        agent_type: Agent type

    Returns:
        Workflow definition dict or None
    """
    phases = WORKFLOW_DEFINITIONS.get(agent_type)
    if not phases:
        return None

    return {
        "agent_type": agent_type,
        "workflow_type": get_workflow_type(agent_type),
        "phases": phases,
        "total_phases": len(phases),
    }
