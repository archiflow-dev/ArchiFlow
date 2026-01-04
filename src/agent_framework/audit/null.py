"""
Null audit trail for testing and development.

A no-op implementation that discards all log messages.
Useful for tests where audit logging is not needed.
"""

import logging
from typing import Dict, Any, Optional
from pathlib import Path

from .trail import AuditTrail

logger = logging.getLogger(__name__)


class NullAuditTrail(AuditTrail):
    """
    No-op audit trail for testing.

    Discards all log messages. Useful for:
    - Unit tests (avoid side effects)
    - Development (reduce log noise)
    - Performance testing (measure without logging overhead)

    Usage:
        audit = NullAuditTrail()

        # All methods do nothing
        await audit.log_execution("read", {}, True)
        await audit.log_security_event("violation", "warning", "Blocked")
        await audit.log_session_event("session_1", "started")
    """

    async def log_execution(
        self,
        tool_name: str,
        params: Dict[str, Any],
        success: bool,
        error: Optional[str] = None,
        **metadata,
    ) -> None:
        """No-op log execution."""
        # Discard log message
        pass

    async def log_security_event(
        self,
        event_type: str,
        severity: str,
        message: str,
        **context,
    ) -> None:
        """No-op log security event."""
        # Discard log message
        pass

    async def log_session_event(
        self,
        session_id: str,
        event_type: str,
        **details,
    ) -> None:
        """No-op log session event."""
        # Discard log message
        pass
