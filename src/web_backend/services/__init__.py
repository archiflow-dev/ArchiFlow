"""
Service layer for ArchiFlow Web Backend.
"""

from .session_service import SessionService
from .workspace_manager import (
    WorkspaceManager,
    WorkspaceSecurityError,
    get_workspace_manager,
)
from .storage_manager import (
    StorageManager,
    StorageLimits,
    StorageLimitError,
    get_storage_manager,
)
from .artifact_service import (
    ArtifactService,
    ArtifactNotFoundError,
)
from .workflow_controller import (
    WorkflowController,
    get_workflow_definition,
    get_workflow_type,
    WORKFLOW_DEFINITIONS,
)
from .agent_registry import (
    AgentRegistry,
    AgentMetadata,
    AgentCapability,
    AgentCategory,
    get_agent_registry,
)
from .session_store import (
    SessionStore,
    SessionInfo,
    get_session_store,
)
from .web_context import (
    WebExecutionContext,
    SandboxMode,
)
from .sandboxed_tool import (
    SandboxedToolWrapper,
    SandboxedToolkit,
    SandboxViolationError,
)
from .audit_logger import (
    AuditLogger,
    AuditEvent,
    AuditEventType,
    AuditSeverity,
    get_audit_logger,
)

__all__ = [
    # Session
    "SessionService",
    "SessionStore",
    "SessionInfo",
    "get_session_store",
    # Workspace
    "WorkspaceManager",
    "WorkspaceSecurityError",
    "get_workspace_manager",
    # Storage
    "StorageManager",
    "StorageLimits",
    "StorageLimitError",
    "get_storage_manager",
    # Artifacts
    "ArtifactService",
    "ArtifactNotFoundError",
    # Workflow
    "WorkflowController",
    "get_workflow_definition",
    "get_workflow_type",
    "WORKFLOW_DEFINITIONS",
    # Agent Registry
    "AgentRegistry",
    "AgentMetadata",
    "AgentCapability",
    "AgentCategory",
    "get_agent_registry",
    # Web Execution Context
    "WebExecutionContext",
    "SandboxMode",
    # Sandboxed Tools
    "SandboxedToolWrapper",
    "SandboxedToolkit",
    "SandboxViolationError",
    # Audit
    "AuditLogger",
    "AuditEvent",
    "AuditEventType",
    "AuditSeverity",
    "get_audit_logger",
]
