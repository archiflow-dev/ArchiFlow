"""
Audit trail interface for logging security events.

Provides abstraction for audit logging across different backends.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime


class AuditSeverity:
    """Audit event severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

    VALUES = [INFO, WARNING, ERROR, CRITICAL]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if severity value is valid."""
        return value in cls.VALUES


class AuditTrail(ABC):
    """
    Interface for audit logging.

    Implementations can log to:
    - Database (persistent storage)
    - File (append-only log files)
    - External service (SIEM, audit system)
    - Console (for debugging/testing)

    All methods should be async and should never raise exceptions
    to avoid disrupting tool execution. Log failures should be
    handled internally (e.g., log to stderr).

    Usage:
        audit = LoggerAuditTrail()

        await audit.log_execution(
            tool_name="read",
            params={"file_path": "config.txt"},
            success=True,
        )

        await audit.log_security_event(
            event_type="path_violation",
            severity=AuditSeverity.WARNING,
            message="Attempted to access path outside workspace",
            requested_path="../../../etc/passwd",
        )
    """

    @abstractmethod
    async def log_execution(
        self,
        tool_name: str,
        params: Dict[str, Any],
        success: bool,
        error: Optional[str] = None,
        **metadata,
    ) -> None:
        """
        Log a tool execution event.

        Args:
            tool_name: Name of the executed tool
            params: Tool parameters (should be sanitized/redacted)
            success: Whether execution succeeded
            error: Error message if failed
            **metadata: Additional metadata (session_id, user_id, etc.)
        """
        pass

    @abstractmethod
    async def log_security_event(
        self,
        event_type: str,
        severity: str,
        message: str,
        **context,
    ) -> None:
        """
        Log a security-related event.

        Use this for:
        - Path traversal attempts
        - Command injection attempts
        - Quota violations
        - Blocked operations

        Args:
            event_type: Type of security event (e.g., "path_violation")
            severity: Severity level (from AuditSeverity)
            message: Human-readable event message
            **context: Additional context (session_id, user_id, etc.)
        """
        pass

    @abstractmethod
    async def log_session_event(
        self,
        session_id: str,
        event_type: str,
        **details,
    ) -> None:
        """
        Log a session lifecycle event.

        Use this for:
        - Session created
        - Session started
        - Session stopped
        - Session paused/resumed

        Args:
            session_id: Session identifier
            event_type: Event type (created, started, stopped, etc.)
            **details: Event details
        """
        pass

    async def log_with_level(
        self,
        level: str,
        message: str,
        **context,
    ) -> None:
        """
        Log with explicit level (convenience method).

        Args:
            level: Log level (info, warning, error, critical)
            message: Log message
            **context: Additional context
        """
        severity_map = {
            "info": AuditSeverity.INFO,
            "warning": AuditSeverity.WARNING,
            "error": AuditSeverity.ERROR,
            "critical": AuditSeverity.CRITICAL,
        }

        severity = severity_map.get(level.lower(), AuditSeverity.INFO)

        await self.log_security_event(
            event_type="general_log",
            severity=severity,
            message=message,
            **context,
        )
