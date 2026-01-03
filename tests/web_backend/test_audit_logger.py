"""
Tests for AuditLogger.
"""

import pytest
import tempfile
import json
from pathlib import Path

from src.web_backend.services.audit_logger import (
    AuditLogger,
    AuditEvent,
    AuditEventType,
    AuditSeverity,
    get_audit_logger,
)
from src.web_backend.services.workspace_manager import WorkspaceManager


class TestAuditEvent:
    """Tests for AuditEvent dataclass."""

    def test_create_event(self):
        """Test creating an audit event."""
        event = AuditEvent(
            event_id="test123",
            timestamp="2024-01-01T00:00:00",
            event_type=AuditEventType.TOOL_CALL,
            severity=AuditSeverity.INFO,
            session_id="session1",
            user_id="user1",
            action="tool:read",
        )

        assert event.event_id == "test123"
        assert event.event_type == AuditEventType.TOOL_CALL
        assert event.success is True

    def test_to_dict(self):
        """Test converting event to dictionary."""
        event = AuditEvent(
            event_id="test123",
            timestamp="2024-01-01T00:00:00",
            event_type=AuditEventType.FILE_WRITE,
            severity=AuditSeverity.WARNING,
            session_id="session1",
            user_id="user1",
            action="file:write",
            details={"path": "test.txt"},
            success=False,
            error="Quota exceeded",
        )

        result = event.to_dict()

        assert result["event_id"] == "test123"
        assert result["event_type"] == "file_write"
        assert result["severity"] == "warning"
        assert result["details"]["path"] == "test.txt"
        assert result["success"] is False
        assert result["error"] == "Quota exceeded"

    def test_to_json_line(self):
        """Test converting event to JSON line."""
        event = AuditEvent(
            event_id="test123",
            timestamp="2024-01-01T00:00:00",
            event_type=AuditEventType.TOOL_CALL,
            severity=AuditSeverity.INFO,
            session_id="session1",
            user_id="user1",
            action="tool:read",
        )

        json_line = event.to_json_line()

        # Should be valid JSON
        parsed = json.loads(json_line)
        assert parsed["event_id"] == "test123"


class TestAuditLogger:
    """Tests for AuditLogger class."""

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
    def logger(self, workspace_manager):
        """Create an AuditLogger."""
        workspace_manager.create_workspace("user1", "session1")
        return AuditLogger(
            base_path=workspace_manager.base_path,
            workspace_manager=workspace_manager,
        )

    def test_log_tool_call_success(self, logger):
        """Test logging a successful tool call."""
        event = logger.log_tool_call(
            session_id="session1",
            user_id="user1",
            tool_name="read",
            parameters={"file_path": "test.txt"},
            success=True,
        )

        assert event.event_type == AuditEventType.TOOL_CALL
        assert event.severity == AuditSeverity.INFO
        assert event.success is True
        assert "read" in event.action

    def test_log_tool_call_failure(self, logger):
        """Test logging a failed tool call."""
        event = logger.log_tool_call(
            session_id="session1",
            user_id="user1",
            tool_name="write",
            parameters={"file_path": "test.txt"},
            success=False,
            error="Permission denied",
        )

        assert event.severity == AuditSeverity.WARNING
        assert event.success is False
        assert event.error == "Permission denied"

    def test_log_file_operation(self, logger):
        """Test logging file operations."""
        event = logger.log_file_operation(
            session_id="session1",
            user_id="user1",
            operation="write",
            path="artifacts/file.txt",
            size=1024,
        )

        assert event.event_type == AuditEventType.FILE_WRITE
        assert event.details["path"] == "artifacts/file.txt"
        assert event.details["size"] == 1024

    def test_log_security_violation(self, logger):
        """Test logging security violations."""
        event = logger.log_security_violation(
            session_id="session1",
            user_id="user1",
            violation_type="path_traversal",
            details={"attempted_path": "../etc/passwd"},
            ip_address="192.168.1.1",
        )

        assert event.event_type == AuditEventType.SECURITY_VIOLATION
        assert event.severity == AuditSeverity.CRITICAL
        assert event.success is False
        assert event.ip_address == "192.168.1.1"

    def test_log_session_event(self, logger):
        """Test logging session lifecycle events."""
        event = logger.log_session_event(
            session_id="session1",
            user_id="user1",
            event_type="start",
            details={"agent_type": "comic"},
        )

        assert event.event_type == AuditEventType.SESSION_START
        assert event.details["agent_type"] == "comic"

    def test_log_workflow_transition(self, logger):
        """Test logging workflow transitions."""
        event = logger.log_workflow_transition(
            session_id="session1",
            user_id="user1",
            from_phase="script_generation",
            to_phase="visual_specification",
            action="approve",
            feedback="Looks good!",
        )

        assert event.event_type == AuditEventType.WORKFLOW_TRANSITION
        assert event.details["from_phase"] == "script_generation"
        assert event.details["to_phase"] == "visual_specification"
        assert event.details["feedback"] == "Looks good!"

    def test_events_persisted_to_file(self, logger, workspace_manager):
        """Test that events are persisted to audit file."""
        logger.log_tool_call(
            session_id="session1",
            user_id="user1",
            tool_name="read",
            parameters={},
            success=True,
        )

        # Check session audit file
        workspace = workspace_manager.get_workspace_path("user1", "session1")
        audit_file = workspace / ".archiflow" / "audit.jsonl"

        assert audit_file.exists()
        lines = audit_file.read_text().strip().split("\n")
        assert len(lines) >= 1

        event = json.loads(lines[0])
        assert event["event_type"] == "tool_call"

    def test_get_session_events(self, logger):
        """Test retrieving session events."""
        # Log some events
        logger.log_tool_call(
            session_id="session1",
            user_id="user1",
            tool_name="read",
            parameters={},
            success=True,
        )
        logger.log_tool_call(
            session_id="session1",
            user_id="user1",
            tool_name="write",
            parameters={},
            success=True,
        )

        events = logger.get_session_events("user1", "session1")

        assert len(events) == 2
        assert all(e.event_type == AuditEventType.TOOL_CALL for e in events)

    def test_get_session_events_filtered(self, logger):
        """Test retrieving filtered session events."""
        logger.log_tool_call(
            session_id="session1",
            user_id="user1",
            tool_name="read",
            parameters={},
            success=True,
        )
        logger.log_file_operation(
            session_id="session1",
            user_id="user1",
            operation="write",
            path="test.txt",
        )

        events = logger.get_session_events(
            "user1", "session1", event_type=AuditEventType.FILE_WRITE
        )

        assert len(events) == 1
        assert events[0].event_type == AuditEventType.FILE_WRITE

    def test_get_session_events_limit(self, logger):
        """Test event retrieval with limit."""
        for i in range(10):
            logger.log_tool_call(
                session_id="session1",
                user_id="user1",
                tool_name=f"tool{i}",
                parameters={},
                success=True,
            )

        events = logger.get_session_events("user1", "session1", limit=5)

        assert len(events) == 5

    def test_get_metrics(self, logger):
        """Test getting audit metrics."""
        logger.log_tool_call(
            session_id="session1",
            user_id="user1",
            tool_name="read",
            parameters={},
            success=True,
        )
        logger.log_tool_call(
            session_id="session1",
            user_id="user1",
            tool_name="write",
            parameters={},
            success=False,
            error="Failed",
        )

        metrics = logger.get_metrics()

        assert "event_counts" in metrics
        assert "total_events" in metrics
        assert metrics["total_events"] >= 2

    def test_event_id_unique(self, logger):
        """Test that event IDs are unique."""
        event1 = logger.log_tool_call(
            session_id="session1",
            user_id="user1",
            tool_name="read",
            parameters={},
            success=True,
        )
        event2 = logger.log_tool_call(
            session_id="session1",
            user_id="user1",
            tool_name="write",
            parameters={},
            success=True,
        )

        assert event1.event_id != event2.event_id

    def test_critical_events_in_global_log(self, logger, workspace_manager):
        """Test that critical events are written to global log."""
        logger.log_security_violation(
            session_id="session1",
            user_id="user1",
            violation_type="test",
            details={},
        )

        # Check global audit file exists
        global_dir = workspace_manager.base_path / ".audit"
        assert global_dir.exists()

        # Should have at least one audit file
        audit_files = list(global_dir.glob("audit-*.jsonl"))
        assert len(audit_files) >= 1

    def test_empty_session_returns_empty_list(self, logger, workspace_manager):
        """Test getting events for session with no audit log."""
        workspace_manager.create_workspace("user2", "session2")

        events = logger.get_session_events("user2", "session2")
        assert events == []
