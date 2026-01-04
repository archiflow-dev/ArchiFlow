"""
Audit Trail Adapter for Web Backend.

Bridges the web backend's AuditLogger to the framework's AuditTrail interface.
"""

import logging
from typing import Optional, Dict, Any

# Import framework interface
try:
    from agent_framework.audit.trail import AuditTrail, AuditSeverity
except ImportError:
    # For standalone testing
    AuditTrail = object
    AuditSeverity = None

from ..services.audit_logger import (
    AuditLogger,
    AuditEventType,
    AuditSeverity as WebAuditSeverity,
)

logger = logging.getLogger(__name__)


class WebAuditTrail(AuditTrail):
    """
    Adapter that bridges AuditLogger to AuditTrail interface.

    This allows the web backend's existing audit logging to work with
    the framework's sandbox runtime.

    The adapter handles:
    - Converting between severity enums
    - Mapping audit event types
    - Passing user_id/session_id context

    Usage:
        audit = WebAuditTrail(
            user_id="user_123",
            session_id="session_456",
            audit_logger=audit_logger,
        )
    """

    # Mapping from framework severity to web severity
    SEVERITY_MAP = {
        "debug": WebAuditSeverity.DEBUG,
        "info": WebAuditSeverity.INFO,
        "warning": WebAuditSeverity.WARNING,
        "error": WebAuditSeverity.ERROR,
        "critical": WebAuditSeverity.CRITICAL,
    }

    def __init__(
        self,
        user_id: str,
        session_id: str,
        audit_logger: Optional[AuditLogger] = None,
    ):
        """
        Initialize the audit trail adapter.

        Args:
            user_id: User ID for this session
            session_id: Session ID
            audit_logger: AuditLogger instance (uses singleton if None)
        """
        from ..services.audit_logger import get_audit_logger

        self.user_id = user_id
        self.session_id = session_id
        self.audit_logger = audit_logger or get_audit_logger()

    def _map_severity(self, severity: str) -> WebAuditSeverity:
        """
        Map framework severity to web backend severity.

        Args:
            severity: Framework severity string

        Returns:
            Web backend severity enum
        """
        return self.SEVERITY_MAP.get(severity.lower(), WebAuditSeverity.INFO)

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
            tool_name: Name of the tool
            params: Tool parameters
            success: Whether execution succeeded
            error: Error message if failed
            **metadata: Additional metadata (user_id, session_id, etc.)
        """
        # Sanitize sensitive parameters before logging
        sanitized_params = self._sanitize_params(params)

        self.audit_logger.log_tool_call(
            session_id=self.session_id,
            user_id=self.user_id,
            tool_name=tool_name,
            parameters=sanitized_params,
            success=success,
            error=error,
        )

    async def log_security_event(
        self,
        event_type: str,
        severity: str,
        message: str,
        **context,
    ) -> None:
        """
        Log a security-related event.

        Args:
            event_type: Type of security event
            severity: Severity level (debug, info, warning, error, critical)
            message: Event message
            **context: Additional context (user_id, session_id, etc.)
        """
        web_severity = self._map_severity(severity)

        # Map event types
        mapped_type = self._map_security_event_type(event_type)

        self.audit_logger.log_security_violation(
            session_id=self.session_id,
            user_id=self.user_id,
            violation_type=mapped_type,
            details={
                "event_type": event_type,
                "message": message,
                **context,
            },
        )

    async def log_session_event(
        self,
        session_id: str,
        event_type: str,
        **details,
    ) -> None:
        """
        Log a session lifecycle event.

        Args:
            session_id: Session identifier (ignored, uses self.session_id)
            event_type: Type of event (created, started, stopped, deleted, etc.)
            **details: Additional details
        """
        # Map event types to web backend's expected types
        mapped_type = self._map_session_event_type(event_type)

        self.audit_logger.log_session_event(
            session_id=self.session_id,
            user_id=self.user_id,
            event_type=mapped_type,
            details=details,
        )

    def _sanitize_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize sensitive parameters before logging.

        Args:
            params: Raw parameters

        Returns:
            Sanitized parameters
        """
        SENSITIVE_KEYS = {
            "password", "passwd", "pwd",
            "api_key", "apikey", "api-key",
            "secret", "token", "auth",
            "credential", "credentials",
            "private_key", "privatekey",
        }

        sanitized = {}
        for key, value in params.items():
            if isinstance(key, str) and key.lower() in SENSITIVE_KEYS:
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, str) and len(value) > 200:
                # Truncate long values
                sanitized[key] = f"{value[:200]}...[truncated {len(value)} chars]"
            else:
                sanitized[key] = value

        return sanitized

    def _map_security_event_type(self, event_type: str) -> str:
        """
        Map framework security event types to web backend format.

        Args:
            event_type: Framework event type

        Returns:
            Web backend event type string
        """
        # Map common event types
        mapping = {
            "path_violation": "path_traversal",
            "command_violation": "dangerous_command",
            "quota_exceeded": "storage_limit",
            "permission_denied": "access_denied",
            "validation_error": "invalid_input",
        }
        return mapping.get(event_type, event_type)

    def _map_session_event_type(self, event_type: str) -> str:
        """
        Map framework session event types to web backend format.

        Args:
            event_type: Framework event type

        Returns:
            Web backend event type string
        """
        # Map common event types
        mapping = {
            "created": "start",
            "started": "start",
            "stopped": "end",
            "deleted": "end",
            "paused": "pause",
            "resumed": "resume",
        }
        return mapping.get(event_type, event_type)

    def get_session_events(
        self,
        event_type: Optional[str] = None,
        limit: int = 100,
    ) -> list:
        """
        Read audit events for the current session.

        Args:
            event_type: Optional filter by event type
            limit: Maximum events to return

        Returns:
            List of AuditEvent objects
        """
        web_event_type = None
        if event_type:
            web_event_type = self._map_security_event_type(event_type)

        return self.audit_logger.get_session_events(
            user_id=self.user_id,
            session_id=self.session_id,
            event_type=web_event_type,
            limit=limit,
        )

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get audit metrics.

        Returns:
            Dictionary of metrics from AuditLogger
        """
        return self.audit_logger.get_metrics()
