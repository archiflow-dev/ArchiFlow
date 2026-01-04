"""
Logger-based audit trail implementation.

Writes audit events to Python logging framework.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from .trail import AuditTrail, AuditSeverity

# Dedicated audit logger
_audit_logger = logging.getLogger("archiflow.audit")


class LoggerAuditTrail(AuditTrail):
    """
    Audit trail that writes to Python logger.

    Logs to the "archiflow.audit" logger at appropriate levels.
    Useful for development and console-based applications.

    Usage:
        audit = LoggerAuditTrail()

        # Logs to archiflow.audit logger
        await audit.log_execution("read", {"file_path": "test.txt"}, True)

    Configuration:
        # In your application setup:
        import logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

        # Or configure audit logger specifically:
        audit_logger = logging.getLogger("archiflow.audit")
        audit_logger.setLevel(logging.INFO)
        handler = logging.FileHandler("audit.log")
        audit_logger.addHandler(handler)
    """

    def __init__(self, logger_name: str = "archiflow.audit"):
        """
        Initialize logger audit trail.

        Args:
            logger_name: Name of the logger to use (default: archiflow.audit)
        """
        self.logger = logging.getLogger(logger_name)

    async def log_execution(
        self,
        tool_name: str,
        params: Dict[str, Any],
        success: bool,
        error: Optional[str] = None,
        **metadata,
    ) -> None:
        """
        Log a tool execution.

        Args:
            tool_name: Name of the tool
            params: Tool parameters
            success: Whether execution succeeded
            error: Error message if failed
            **metadata: Additional metadata
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        status = "SUCCESS" if success else "FAILED"

        # Format params for log (truncate if needed)
        params_str = self._format_params(params)

        message = (
            f"{timestamp} | TOOL_EXECUTION | {status} | "
            f"tool={tool_name} | params={params_str}"
        )

        if error:
            message += f" | error={error}"

        # Add session info if present
        session_id = metadata.get("session_id")
        if session_id:
            message += f" | session={session_id}"

        # Log at appropriate level
        if success:
            self.logger.info(message)
        else:
            self.logger.warning(message)

    async def log_security_event(
        self,
        event_type: str,
        severity: str,
        message: str,
        **context,
    ) -> None:
        """
        Log a security event.

        Args:
            event_type: Type of security event
            severity: Severity level
            message: Event message
            **context: Additional context
        """
        timestamp = datetime.now(timezone.utc).isoformat()

        # Format context
        context_str = self._format_context(context)

        log_message = (
            f"{timestamp} | SECURITY_EVENT | {event_type} | "
            f"{severity} | {message} | {context_str}"
        )

        # Map severity to logging level
        log_fn = self._get_log_function(severity)

        # Log
        log_fn(log_message)

    async def log_session_event(
        self,
        session_id: str,
        event_type: str,
        **details,
    ) -> None:
        """
        Log a session lifecycle event.

        Args:
            session_id: Session identifier
            event_type: Event type
            **details: Event details
        """
        timestamp = datetime.now(timezone.utc).isoformat()

        # Format details
        details_str = self._format_context(details)

        message = (
            f"{timestamp} | SESSION_EVENT | {event_type} | "
            f"session={session_id} | {details_str}"
        )

        self.logger.info(message)

    def _format_params(self, params: Dict[str, Any]) -> str:
        """Format params for logging (truncate if needed, redact sensitive)."""
        if not params:
            return "{}"

        # Sensitive parameter names to redact
        SENSITIVE_KEYS = {
            "password", "passwd", "pwd",
            "api_key", "apikey", "api-key",
            "secret", "token", "auth",
            "credential", "credentials",
            "private_key", "privatekey",
        }

        # Truncate long values and redact sensitive data
        formatted = {}
        for key, value in params.items():
            # Check if this is a sensitive key (case-insensitive)
            is_sensitive = key.lower() in SENSITIVE_KEYS

            if is_sensitive:
                formatted[key] = "[REDACTED]"
            elif isinstance(value, str) and len(value) > 100:
                formatted[key] = f"{value[:100]}...[truncated {len(value)} chars]"
            else:
                formatted[key] = value

        return str(formatted)

    def _format_context(self, context: Dict[str, Any]) -> str:
        """Format context dict for logging."""
        if not context:
            return ""

        parts = []
        for key, value in context.items():
            if isinstance(value, str):
                parts.append(f"{key}={value}")
            elif isinstance(value, (int, float, bool)):
                parts.append(f"{key}={value}")
            else:
                parts.append(f"{key}={type(value).__name__}")

        return " | ".join(parts)

    def _get_log_function(self, severity: str):
        """Get logging function for severity level."""
        severity_map = {
            AuditSeverity.INFO: self.logger.info,
            AuditSeverity.WARNING: self.logger.warning,
            AuditSeverity.ERROR: self.logger.error,
            AuditSeverity.CRITICAL: self.logger.critical,
        }

        # Default to info if unknown severity
        return severity_map.get(severity, self.logger.info)
