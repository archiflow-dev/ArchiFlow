"""
Tests for WorkflowController.
"""

import pytest
import tempfile
import asyncio
from pathlib import Path

from src.web_backend.services.workflow_controller import (
    WorkflowController,
    get_workflow_definition,
    get_workflow_type,
    WORKFLOW_DEFINITIONS,
)
from src.web_backend.schemas.workflow import PhaseStatus
from src.web_backend.services.workspace_manager import WorkspaceManager


class TestWorkflowDefinitions:
    """Tests for workflow definition functions."""

    def test_workflow_definitions_exist(self):
        """Test that workflow definitions are defined."""
        assert "comic" in WORKFLOW_DEFINITIONS
        assert "ppt" in WORKFLOW_DEFINITIONS
        assert "coding" in WORKFLOW_DEFINITIONS
        assert "research" in WORKFLOW_DEFINITIONS

    def test_comic_workflow_phases(self):
        """Test comic workflow has correct phases."""
        phases = WORKFLOW_DEFINITIONS["comic"]
        phase_ids = [p["id"] for p in phases]

        assert "script_generation" in phase_ids
        assert "visual_specification" in phase_ids
        assert "character_references" in phase_ids
        assert "panel_generation" in phase_ids
        assert "export" in phase_ids

    def test_workflow_phase_order(self):
        """Test that phases have sequential order."""
        for agent_type, phases in WORKFLOW_DEFINITIONS.items():
            orders = [p["order"] for p in phases]
            assert orders == list(range(1, len(phases) + 1)), f"Invalid order for {agent_type}"

    def test_get_workflow_type_phase_heavy(self):
        """Test workflow type detection for phase-heavy agents."""
        assert get_workflow_type("comic") == "phase_heavy"
        assert get_workflow_type("ppt") == "phase_heavy"

    def test_get_workflow_type_chat_heavy(self):
        """Test workflow type detection for chat-heavy agents."""
        assert get_workflow_type("coding") == "chat_heavy"
        assert get_workflow_type("research") == "chat_heavy"

    def test_get_workflow_definition_comic(self):
        """Test getting workflow definition for comic agent."""
        definition = get_workflow_definition("comic")

        assert definition is not None
        assert definition["agent_type"] == "comic"
        assert definition["workflow_type"] == "phase_heavy"
        assert definition["total_phases"] == 5
        assert len(definition["phases"]) == 5

    def test_get_workflow_definition_unknown(self):
        """Test getting workflow definition for unknown agent."""
        definition = get_workflow_definition("unknown_agent")
        assert definition is None


class TestWorkflowController:
    """Tests for WorkflowController class."""

    @pytest.fixture
    def temp_base(self):
        """Create a temporary directory for workspaces."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def workspace_manager(self, temp_base):
        """Create a WorkspaceManager."""
        return WorkspaceManager(base_path=temp_base)

    @pytest.fixture
    def controller(self, workspace_manager, monkeypatch):
        """Create a WorkflowController for comic agent."""
        # Monkeypatch the workspace manager getter
        monkeypatch.setattr(
            "src.web_backend.services.workflow_controller.get_workspace_manager",
            lambda: workspace_manager,
        )
        workspace_manager.create_workspace("default_user", "test_session")
        return WorkflowController(
            session_id="test_session",
            agent_type="comic",
            user_id="default_user",
        )

    def test_init_loads_phases(self, controller):
        """Test that initialization loads phases."""
        assert len(controller.phases) == 5
        assert controller.phases[0].id == "script_generation"

    def test_initial_state(self, controller):
        """Test initial workflow state."""
        state = asyncio.run(controller.get_current_state())

        assert state.session_id == "test_session"
        assert state.agent_type == "comic"
        assert state.current_phase is None
        assert len(state.phases) == 5
        assert all(p.status == PhaseStatus.PENDING for p in state.phases)

    def test_start_workflow(self, controller):
        """Test starting the workflow."""
        state = asyncio.run(controller.start_workflow())

        assert state.current_phase == "script_generation"
        assert state.phases[0].status == PhaseStatus.IN_PROGRESS
        assert state.phases[0].started_at is not None

    def test_set_phase_awaiting_approval(self, controller):
        """Test setting a phase to awaiting approval."""
        asyncio.run(controller.start_workflow())
        state = asyncio.run(
            controller.set_phase_awaiting_approval("script_generation")
        )

        assert state.phases[0].status == PhaseStatus.AWAITING_APPROVAL

    def test_approve_phase(self, controller):
        """Test approving a phase."""
        asyncio.run(controller.start_workflow())
        asyncio.run(controller.set_phase_awaiting_approval("script_generation"))
        state = asyncio.run(controller.approve_phase("script_generation"))

        assert state.phases[0].status == PhaseStatus.APPROVED
        assert state.phases[0].completed_at is not None
        assert state.current_phase == "visual_specification"
        assert state.phases[1].status == PhaseStatus.IN_PROGRESS

    def test_reject_phase(self, controller):
        """Test rejecting a phase."""
        asyncio.run(controller.start_workflow())
        asyncio.run(controller.set_phase_awaiting_approval("script_generation"))
        state = asyncio.run(
            controller.reject_phase("script_generation", "Needs more detail")
        )

        assert state.phases[0].status == PhaseStatus.REJECTED
        # Phase should still be current for revision
        assert state.current_phase == "script_generation"

    def test_complete_phase(self, controller):
        """Test completing a phase without approval."""
        asyncio.run(controller.start_workflow())
        state = asyncio.run(controller.complete_phase("script_generation"))

        assert state.phases[0].status == PhaseStatus.COMPLETED
        assert state.current_phase == "visual_specification"

    def test_progress_calculation(self, controller):
        """Test progress percentage calculation."""
        state = asyncio.run(controller.start_workflow())
        assert state.progress_percent == 0.0

        asyncio.run(controller.approve_phase("script_generation"))
        state = asyncio.run(controller.get_current_state())
        assert state.progress_percent == 20.0  # 1/5 = 20%

        asyncio.run(controller.approve_phase("visual_specification"))
        state = asyncio.run(controller.get_current_state())
        assert state.progress_percent == 40.0  # 2/5 = 40%

    def test_complete_all_phases(self, controller):
        """Test completing all phases."""
        asyncio.run(controller.start_workflow())

        phase_ids = [
            "script_generation",
            "visual_specification",
            "character_references",
            "panel_generation",
            "export",
        ]

        for phase_id in phase_ids:
            asyncio.run(controller.approve_phase(phase_id))

        state = asyncio.run(controller.get_current_state())
        assert state.progress_percent == 100.0
        assert state.current_phase is None

    def test_reset_workflow(self, controller):
        """Test resetting the workflow."""
        asyncio.run(controller.start_workflow())
        asyncio.run(controller.approve_phase("script_generation"))

        state = asyncio.run(controller.reset_workflow())

        assert state.current_phase is None
        assert all(p.status == PhaseStatus.PENDING for p in state.phases)
        assert all(p.started_at is None for p in state.phases)
        assert all(p.completed_at is None for p in state.phases)

    def test_invalid_phase_id(self, controller):
        """Test handling invalid phase ID."""
        asyncio.run(controller.start_workflow())

        with pytest.raises(ValueError) as exc_info:
            asyncio.run(controller.approve_phase("invalid_phase"))

        assert "not found" in str(exc_info.value)

    def test_state_persistence(self, workspace_manager, monkeypatch):
        """Test that workflow state is persisted and restored."""
        monkeypatch.setattr(
            "src.web_backend.services.workflow_controller.get_workspace_manager",
            lambda: workspace_manager,
        )
        workspace_manager.create_workspace("default_user", "persist_test")

        # Create controller and advance workflow
        controller1 = WorkflowController(
            session_id="persist_test",
            agent_type="comic",
            user_id="default_user",
        )
        asyncio.run(controller1.start_workflow())
        asyncio.run(controller1.approve_phase("script_generation"))

        # Create new controller - should restore state
        controller2 = WorkflowController(
            session_id="persist_test",
            agent_type="comic",
            user_id="default_user",
        )

        state = asyncio.run(controller2.get_current_state())
        assert state.current_phase == "visual_specification"
        assert state.phases[0].status == PhaseStatus.APPROVED

    def test_workflow_metadata(self, controller):
        """Test workflow metadata in state."""
        state = asyncio.run(controller.get_current_state())

        assert "workflow_type" in state.metadata
        assert state.metadata["workflow_type"] == "phase_heavy"


class TestChatHeavyWorkflow:
    """Tests for chat-heavy workflow agents."""

    @pytest.fixture
    def temp_base(self):
        """Create a temporary directory for workspaces."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def workspace_manager(self, temp_base):
        """Create a WorkspaceManager."""
        return WorkspaceManager(base_path=temp_base)

    @pytest.fixture
    def controller(self, workspace_manager, monkeypatch):
        """Create a WorkflowController for coding agent."""
        monkeypatch.setattr(
            "src.web_backend.services.workflow_controller.get_workspace_manager",
            lambda: workspace_manager,
        )
        workspace_manager.create_workspace("default_user", "coding_session")
        return WorkflowController(
            session_id="coding_session",
            agent_type="coding",
            user_id="default_user",
        )

    def test_coding_workflow_phases(self, controller):
        """Test coding agent has correct phases."""
        assert len(controller.phases) == 3
        phase_ids = [p.id for p in controller.phases]
        assert "planning" in phase_ids
        assert "implementation" in phase_ids
        assert "verification" in phase_ids

    def test_no_approval_required(self, controller):
        """Test that coding phases don't require approval."""
        definition = get_workflow_definition("coding")
        for phase in definition["phases"]:
            assert phase["requires_approval"] is False
