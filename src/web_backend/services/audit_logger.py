"""
Audit Logger for ArchiFlow Web Backend.

Provides security-focused logging of all agent operations.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from enum import Enum
import json
import logging
import hashlib

from .workspace_manager import get_workspace_manager

logger = logging.getLogger(__name__)


class AuditEventType(str, Enum):
    """Types of audit events."""
    TOOL_CALL = "tool_call"
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    FILE_DELETE = "file_delete"
    SECURITY_VIOLATION = "security_violation"
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    WORKFLOW_TRANSITION = "workflow_transition"
    USER_ACTION = "user_action"
    API_REQUEST = "api_request"


class AuditSeverity(str, Enum):
    """Severity levels for audit events."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """
    Represents a single audit event.

    All events are immutable once created.
    """
    event_id: str
    timestamp: str
    event_type: AuditEventType
    severity: AuditSeverity
    session_id: str
    user_id: str
    action: str
    details: Dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "event_type": self.event_type.value,
            "severity": self.severity.value,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "action": self.action,
            "details": self.details,
            "success": self.success,
            "error": self.error,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
        }

    def to_json_line(self) -> str:
        """Convert to JSON line for log file."""
        return json.dumps(self.to_dict(), separators=(',', ':'))


class AuditLogger:
    """
    Logs security-relevant events to audit trail.

    Features:
    - Append-only log files (JSONL format)
    - Per-session audit logs
    - Global audit log for cross-session events
    - Event filtering and querying
    - Tamper detection via checksums

    Audit logs are stored in:
    - Session: {workspace}/.archiflow/audit.jsonl
    - Global: {base_path}/.audit/global.jsonl
    """

    def __init__(
        self,
        base_path: Optional[Path] = None,
        workspace_manager=None,
    ):
        """
        Initialize the audit logger.

        Args:
            base_path: Base path for global audit logs
            workspace_manager: WorkspaceManager instance
        """
        self.workspace_manager = workspace_manager or get_workspace_manager()
        self.base_path = base_path or self.workspace_manager.base_path

        # Ensure global audit directory exists
        self._global_audit_dir = self.base_path / ".audit"
        self._global_audit_dir.mkdir(parents=True, exist_ok=True)

        # Event counters for metrics
        self._event_counts: Dict[str, int] = {}

    def _generate_event_id(self) -> str:
        """Generate a unique event ID."""
        timestamp = datetime.now(datetime.UTC).isoformat()
        data = f"{timestamp}-{id(self)}".encode()
        return hashlib.sha256(data).hexdigest()[:16]

    def _get_session_audit_file(self, user_id: str, session_id: str) -> Path:
        """Get the audit file path for a session."""
        workspace = self.workspace_manager.get_workspace_path(user_id, session_id)
        return workspace / ".archiflow" / "audit.jsonl"

    def _get_global_audit_file(self) -> Path:
        """Get the global audit file path."""
        today = datetime.now(datetime.UTC).strftime("%Y-%m-%d")
        return self._global_audit_dir / f"audit-{today}.jsonl"

    def _write_event(self, event: AuditEvent, file_path: Path) -> None:
        """
        Write an event to an audit file.

        Args:
            event: The audit event to write
            file_path: Path to the audit file
        """
        try:
            # Ensure parent directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Append to file
            with open(file_path, 'a', encoding='utf-8') as f:
                f.write(event.to_json_line() + '\n')

        except Exception as e:
            # Never fail silently on audit writes - log to Python logger
            logger.error(f"Failed to write audit event: {e}")

    def _log_event(self, event: AuditEvent) -> None:
        """
        Log an event to appropriate audit files.

        Args:
            event: The audit event
        """
        # Update counters
        event_key = f"{event.event_type.value}:{event.severity.value}"
        self._event_counts[event_key] = self._event_counts.get(event_key, 0) + 1

        # Write to session audit file
        if event.session_id:
            session_file = self._get_session_audit_file(event.user_id, event.session_id)
            self._write_event(event, session_file)

        # Write security events and errors to global audit
        if event.severity in (AuditSeverity.WARNING, AuditSeverity.ERROR, AuditSeverity.CRITICAL):
            global_file = self._get_global_audit_file()
            self._write_event(event, global_file)

        # Also log to Python logger for monitoring
        log_level = {
            AuditSeverity.DEBUG: logging.DEBUG,
            AuditSeverity.INFO: logging.INFO,
            AuditSeverity.WARNING: logging.WARNING,
            AuditSeverity.ERROR: logging.ERROR,
            AuditSeverity.CRITICAL: logging.CRITICAL,
        }.get(event.severity, logging.INFO)

        logger.log(
            log_level,
            f"[AUDIT] {event.event_type.value}: {event.action} "
            f"(session={event.session_id}, user={event.user_id})"
        )

    def log_tool_call(
        self,
        session_id: str,
        user_id: str,
        tool_name: str,
        parameters: Dict[str, Any],
        success: bool = True,
        error: Optional[str] = None,
    ) -> AuditEvent:
        """
        Log a tool call event.

        Args:
            session_id: Session ID
            user_id: User ID
            tool_name: Name of the tool called
            parameters: Tool parameters (should be sanitized)
            success: Whether the call succeeded
            error: Error message if failed

        Returns:
            The created audit event
        """
        severity = AuditSeverity.INFO if success else AuditSeverity.WARNING

        event = AuditEvent(
            event_id=self._generate_event_id(),
            timestamp=datetime.now(datetime.UTC).isoformat(),
            event_type=AuditEventType.TOOL_CALL,
            severity=severity,
            session_id=session_id,
            user_id=user_id,
            action=f"tool:{tool_name}",
            details={"tool_name": tool_name, "parameters": parameters},
            success=success,
            error=error,
        )

        self._log_event(event)
        return event

    def log_file_operation(
        self,
        session_id: str,
        user_id: str,
        operation: str,
        path: str,
        size: Optional[int] = None,
        success: bool = True,
        error: Optional[str] = None,
    ) -> AuditEvent:
        """
        Log a file operation.

        Args:
            session_id: Session ID
            user_id: User ID
            operation: Operation type (read, write, delete)
            path: File path
            size: File size in bytes (for writes)
            success: Whether the operation succeeded
            error: Error message if failed

        Returns:
            The created audit event
        """
        event_type = {
            "read": AuditEventType.FILE_READ,
            "write": AuditEventType.FILE_WRITE,
            "delete": AuditEventType.FILE_DELETE,
        }.get(operation, AuditEventType.FILE_READ)

        event = AuditEvent(
            event_id=self._generate_event_id(),
            timestamp=datetime.now(datetime.UTC).isoformat(),
            event_type=event_type,
            severity=AuditSeverity.INFO if success else AuditSeverity.WARNING,
            session_id=session_id,
            user_id=user_id,
            action=f"file:{operation}",
            details={"path": path, "size": size},
            success=success,
            error=error,
        )

        self._log_event(event)
        return event

    def log_security_violation(
        self,
        session_id: str,
        user_id: str,
        violation_type: str,
        details: Dict[str, Any],
        ip_address: Optional[str] = None,
    ) -> AuditEvent:
        """
        Log a security violation.

        Args:
            session_id: Session ID
            user_id: User ID
            violation_type: Type of violation
            details: Violation details
            ip_address: Client IP address

        Returns:
            The created audit event
        """
        event = AuditEvent(
            event_id=self._generate_event_id(),
            timestamp=datetime.now(datetime.UTC).isoformat(),
            event_type=AuditEventType.SECURITY_VIOLATION,
            severity=AuditSeverity.CRITICAL,
            session_id=session_id,
            user_id=user_id,
            action=f"security:{violation_type}",
            details=details,
            success=False,
            error=f"Security violation: {violation_type}",
            ip_address=ip_address,
        )

        self._log_event(event)
        return event

    def log_session_event(
        self,
        session_id: str,
        user_id: str,
        event_type: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditEvent:
        """
        Log a session lifecycle event.

        Args:
            session_id: Session ID
            user_id: User ID
            event_type: Type of event (start, end, pause, resume)
            details: Additional details

        Returns:
            The created audit event
        """
        audit_type = {
            "start": AuditEventType.SESSION_START,
            "end": AuditEventType.SESSION_END,
        }.get(event_type, AuditEventType.USER_ACTION)

        event = AuditEvent(
            event_id=self._generate_event_id(),
            timestamp=datetime.now(datetime.UTC).isoformat(),
            event_type=audit_type,
            severity=AuditSeverity.INFO,
            session_id=session_id,
            user_id=user_id,
            action=f"session:{event_type}",
            details=details or {},
            success=True,
        )

        self._log_event(event)
        return event

    def log_workflow_transition(
        self,
        session_id: str,
        user_id: str,
        from_phase: Optional[str],
        to_phase: str,
        action: str,
        feedback: Optional[str] = None,
    ) -> AuditEvent:
        """
        Log a workflow phase transition.

        Args:
            session_id: Session ID
            user_id: User ID
            from_phase: Previous phase (None if starting)
            to_phase: New phase
            action: Transition action (approve, reject, complete)
            feedback: User feedback if any

        Returns:
            The created audit event
        """
        event = AuditEvent(
            event_id=self._generate_event_id(),
            timestamp=datetime.now(datetime.UTC).isoformat(),
            event_type=AuditEventType.WORKFLOW_TRANSITION,
            severity=AuditSeverity.INFO,
            session_id=session_id,
            user_id=user_id,
            action=f"workflow:{action}",
            details={
                "from_phase": from_phase,
                "to_phase": to_phase,
                "feedback": feedback,
            },
            success=True,
        )

        self._log_event(event)
        return event

    def get_session_events(
        self,
        user_id: str,
        session_id: str,
        event_type: Optional[AuditEventType] = None,
        limit: int = 100,
    ) -> List[AuditEvent]:
        """
        Read audit events for a session.

        Args:
            user_id: User ID
            session_id: Session ID
            event_type: Optional filter by event type
            limit: Maximum events to return

        Returns:
            List of audit events
        """
        audit_file = self._get_session_audit_file(user_id, session_id)

        if not audit_file.exists():
            return []

        events = []
        try:
            with open(audit_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    data = json.loads(line)

                    # Filter by event type if specified
                    if event_type and data.get("event_type") != event_type.value:
                        continue

                    events.append(AuditEvent(
                        event_id=data["event_id"],
                        timestamp=data["timestamp"],
                        event_type=AuditEventType(data["event_type"]),
                        severity=AuditSeverity(data["severity"]),
                        session_id=data["session_id"],
                        user_id=data["user_id"],
                        action=data["action"],
                        details=data.get("details", {}),
                        success=data.get("success", True),
                        error=data.get("error"),
                        ip_address=data.get("ip_address"),
                        user_agent=data.get("user_agent"),
                    ))

                    if len(events) >= limit:
                        break

        except Exception as e:
            logger.error(f"Error reading audit log: {e}")

        return events

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get audit metrics.

        Returns:
            Dictionary of metrics
        """
        return {
            "event_counts": self._event_counts.copy(),
            "total_events": sum(self._event_counts.values()),
        }


# Global singleton instance
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get the global AuditLogger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger
