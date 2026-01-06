"""
Service layer for ArchiFlow Web Backend.

Phase 4 Notes:
    - Framework sandbox architecture (SessionRuntimeManager) is now the ONLY architecture
    - Legacy architecture (SandboxedToolWrapper) has been removed
    - Adapters (WebStorageQuota, WebAuditTrail) bridge web components to framework
    - WebAgentFactory is simplified with only framework code path
    - Feature flag USE_FRAMEWORK_SANDBOX has been removed

Architecture:
    The web backend now exclusively uses agent_framework's SessionRuntimeManager
    for all sandbox operations. This provides:
    - Centralized security policy management
    - Better performance (no tool wrapping overhead)
    - Reusability across all interfaces
    - Easier testing and maintenance
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
    SandboxedToolRegistry,
    SandboxViolationError,
)
from .audit_logger import (
    AuditLogger,
    AuditEvent,
    AuditEventType,
    AuditSeverity,
    get_audit_logger,
)
from .web_agent_factory import (
    WebAgentFactory,
    get_web_agent_factory,
    init_web_agent_factory,
)
from .agent_runner import (
    WebAgentRunner,
    AgentRunnerPool,
    AgentExecutionError,
    get_runner_pool,
)
from .web_session_broker import (
    WebSessionBroker,
    WebSessionBrokerError,
)
from .agent_session_manager import (
    AgentSessionManager,
    get_agent_session_manager,
)
from .comment_service import (
    CommentService,
    CommentNotFoundError,
    CommentServiceError,
    get_comment_service,
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
    "SandboxedToolRegistry",
    "SandboxViolationError",
    # Audit
    "AuditLogger",
    "AuditEvent",
    "AuditEventType",
    "AuditSeverity",
    "get_audit_logger",
    # Agent Factory
    "WebAgentFactory",
    "get_web_agent_factory",
    "init_web_agent_factory",
    # Agent Runner
    "WebAgentRunner",
    "AgentRunnerPool",
    "AgentExecutionError",
    "get_runner_pool",
    # Session Broker
    "WebSessionBroker",
    "WebSessionBrokerError",
    # Agent Session Manager
    "AgentSessionManager",
    "get_agent_session_manager",
    # Comment Service
    "CommentService",
    "CommentNotFoundError",
    "CommentServiceError",
    "get_comment_service",
]

