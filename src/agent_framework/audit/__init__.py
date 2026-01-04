"""
Audit trail interfaces and implementations for logging security events.

This package provides interfaces and implementations for audit logging.
"""

from .trail import AuditTrail, AuditSeverity
from .null import NullAuditTrail
from .logger import LoggerAuditTrail

__all__ = [
    "AuditTrail",
    "AuditSeverity",
    "NullAuditTrail",
    "LoggerAuditTrail",
]
