"""
Web Backend Adapters Package.

This package provides adapters that bridge the web backend's existing
components (StorageManager, AuditLogger) to the framework's interfaces
(StorageQuota, AuditTrail).

These adapters enable the framework's sandbox runtime to work seamlessly
with the web backend's infrastructure without requiring changes to
either system's core implementation.

Phase 4 Notes:
    - These adapters are now the STANDARD way to integrate with framework sandbox
    - WebAgentFactory exclusively uses SessionRuntimeManager with these adapters
    - Legacy SandboxedToolWrapper path has been removed

Components:
    WebStorageQuota - Adapts StorageManager to StorageQuota interface
    WebAuditTrail - Adapts AuditLogger to AuditTrail interface

Usage:
    from web_backend.adapters import WebStorageQuota, WebAuditTrail

    quota = WebStorageQuota(user_id="user_123", session_id="session_456")
    audit = WebAuditTrail(user_id="user_123", session_id="session_456")

    # Use with sandbox runtime
    from agent_framework.runtime.session_manager import SessionRuntimeManager
    from agent_framework.runtime.manager import RuntimeManager

    manager = SessionRuntimeManager(
        session_id="session_456",
        workspace_path=workspace_path,
        global_manager=RuntimeManager(),
        storage_quota=quota,
        audit_trail=audit,
    )
"""

from .storage import WebStorageQuota
from .audit import WebAuditTrail

__all__ = [
    "WebStorageQuota",
    "WebAuditTrail",
]
