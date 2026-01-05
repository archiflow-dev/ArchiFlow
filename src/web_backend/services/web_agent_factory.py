"""
Web Agent Factory for ArchiFlow Web Backend.

Creates agents with sandboxed tools for secure web execution.

This module uses the framework's SessionRuntimeManager for sandboxing:
- Framework-level path validation, command validation, quota enforcement
- Cleaner separation of concerns
- Better reusability across all interfaces (web, CLI, future APIs)

Architecture:
    - Uses agent_framework.runtime.SessionRuntimeManager
    - Framework-level validation and enforcement
    - Web backend provides adapters (WebStorageQuota, WebAuditTrail) for integration

Usage:
    factory = WebAgentFactory(
        workspace_manager=workspace_manager,
        storage_manager=storage_manager,
        audit_logger=audit_logger,
    )

    agent = await factory.create_agent(
        agent_type="coding",
        session_id="session_123",
        user_id="user_456",
    )
"""

from typing import Optional, List, Dict, Any, TYPE_CHECKING
from pathlib import Path
import logging

from agent_framework.runtime.context import ExecutionContext
from agent_framework.runtime.manager import RuntimeManager
from agent_framework.runtime.local import LocalRuntime

from .web_context import WebExecutionContext, SandboxMode
from .workspace_manager import WorkspaceManager
from .storage_manager import StorageManager
from .audit_logger import AuditLogger

if TYPE_CHECKING:
    from agent_framework.agents.base import BaseAgent

logger = logging.getLogger(__name__)


class WebAgentFactory:
    """
    Factory for creating agents with sandboxed tools.

    This factory creates agents configured for secure web execution:
    - All file tools are sandboxed at framework level
    - Paths are validated against the session workspace
    - Storage quotas are enforced
    - All operations are audit logged

    Architecture:
        Uses agent_framework.runtime.SessionRuntimeManager for sandboxing.
        The framework handles path validation, command validation, and quota
        enforcement. Web backend provides adapters for storage and audit.

    Usage:
        factory = WebAgentFactory(
            workspace_manager=workspace_manager,
            storage_manager=storage_manager,
            audit_logger=audit_logger,
        )

        agent = await factory.create_agent(
            agent_type="coding",
            session_id="session_123",
            user_id="user_456",
        )
    """

    def __init__(
        self,
        workspace_manager: WorkspaceManager,
        storage_manager: Optional[StorageManager] = None,
        audit_logger: Optional[AuditLogger] = None,
        sandbox_mode: SandboxMode = SandboxMode.STRICT,
    ):
        """
        Initialize the factory.

        Args:
            workspace_manager: Manager for session workspaces
            storage_manager: Optional manager for storage quotas
            audit_logger: Optional logger for audit trail
            sandbox_mode: Sandbox enforcement level
        """
        self.workspace_manager = workspace_manager
        self.storage_manager = storage_manager
        self.audit_logger = audit_logger
        self.sandbox_mode = sandbox_mode

        # Create global runtime manager
        self._runtime_manager = RuntimeManager()
        self._runtime_manager.register_runtime("local", LocalRuntime())

        logger.info(
            f"WebAgentFactory initialized: sandbox_mode={sandbox_mode.value}, "
            f"architecture=FRAMEWORK (SessionRuntimeManager)"
        )

    def create_execution_context(
        self,
        session_id: str,
        user_id: str,
        workspace_path: Optional[Path] = None,
        **kwargs
    ) -> WebExecutionContext:
        """
        Create a sandboxed execution context for a session.

        Args:
            session_id: Session identifier
            user_id: User identifier
            workspace_path: Optional explicit workspace path
            **kwargs: Additional context options

        Returns:
            Configured WebExecutionContext
        """
        # Get or create workspace path
        if workspace_path is None:
            workspace_path = self.workspace_manager.get_workspace_path(user_id, session_id)

        # Ensure workspace exists
        if not workspace_path.exists():
            self.workspace_manager.create_workspace(user_id, session_id)

        return WebExecutionContext(
            session_id=session_id,
            user_id=user_id,
            workspace_path=workspace_path,
            workspace_manager=self.workspace_manager,
            storage_manager=self.storage_manager,
            audit_logger=self.audit_logger,
            sandbox_mode=self.sandbox_mode,
            working_directory=str(workspace_path),
            allowed_network=kwargs.get("allowed_network", True),
            timeout=kwargs.get("timeout", 60),
            max_memory_mb=kwargs.get("max_memory_mb", 512),
            max_cpu_percent=kwargs.get("max_cpu_percent", 80),
            tool_overrides={
                # Force bash to run in workspace directory
                "bash": {"working_directory": str(workspace_path)},
                "restricted_bash": {"working_directory": str(workspace_path)},
            }
        )

    async def _setup_agent_sandbox(
        self,
        agent: "BaseAgent",
        context: WebExecutionContext,
    ) -> None:
        """
        Setup agent with framework SessionRuntimeManager.

        This creates a SessionRuntimeManager that:
        - Wraps file tools with path validation and quota enforcement
        - Delegates non-file tools to the global RuntimeManager
        - Uses web backend's storage/audit via adapters

        Args:
            agent: The agent to configure
            context: Execution context
        """
        from ..adapters import WebStorageQuota, WebAuditTrail
        from agent_framework.runtime.session_manager import SessionRuntimeManager
        from agent_framework.runtime.sandbox import SandboxMode as FrameworkSandboxMode

        # Map sandbox mode
        mode_map = {
            SandboxMode.DISABLED: FrameworkSandboxMode.DISABLED,
            SandboxMode.PERMISSIVE: FrameworkSandboxMode.PERMISSIVE,
            SandboxMode.STRICT: FrameworkSandboxMode.STRICT,
        }
        framework_mode = mode_map.get(self.sandbox_mode, FrameworkSandboxMode.STRICT)

        # Create storage quota adapter
        storage_quota = None
        if self.storage_manager:
            storage_quota = WebStorageQuota(
                user_id=context.user_id,
                session_id=context.session_id,
                storage_manager=self.storage_manager,
            )

        # Create audit trail adapter
        audit_trail = None
        if self.audit_logger:
            audit_trail = WebAuditTrail(
                user_id=context.user_id,
                session_id=context.session_id,
                audit_logger=self.audit_logger,
            )

        # Create session runtime manager
        session_manager = self._runtime_manager.create_session_manager(
            session_id=context.session_id,
            workspace_path=context.workspace_path,
            storage_quota=storage_quota,
            audit_trail=audit_trail,
            sandbox_mode=framework_mode,
        )

        # Store on agent for use during execution
        agent._session_runtime_manager = session_manager

        # Configure agent's tools to use the session manager
        # The SessionRuntimeManager intercepts tool.execute() calls
        # for file tools and applies sandbox validation
        if hasattr(agent, 'tools') and agent.tools:
            # agent.tools is a ToolRegistry, call list_tools() to get actual tools
            tools_list = agent.tools.list_tools() if hasattr(agent.tools, 'list_tools') else []
            logger.info(f"🔧 Configuring {len(tools_list)} tools with session manager")
            for tool in tools_list:
                # Inject session manager into tools that support it
                if hasattr(tool, '_session_runtime_manager'):
                    tool._session_runtime_manager = session_manager

                # Log execution context for file tools
                if hasattr(tool, 'execution_context') and tool.execution_context:
                    logger.info(
                        f"   Tool '{tool.name}': working_directory={tool.execution_context.working_directory}"
                    )

        logger.info(
            f"Configured agent with framework SessionRuntimeManager "
            f"(mode={framework_mode}, quota={storage_quota is not None}, "
            f"audit={audit_trail is not None})"
        )

    async def create_agent(
        self,
        agent_type: str,
        session_id: str,
        user_id: str,
        user_prompt: Optional[str] = None,
        project_directory: Optional[str] = None,
        **kwargs
    ) -> "BaseAgent":
        """
        Create an agent with sandboxed tools.

        Args:
            agent_type: Type of agent to create (coding, comic, ppt, etc.)
            session_id: Session identifier
            user_id: User identifier
            user_prompt: Initial user prompt
            project_directory: Ignored for web (workspace is used instead)
            **kwargs: Additional agent options

        Returns:
            Configured agent instance with sandboxed tools

        Raises:
            ValueError: If agent type is not supported
        """
        # Import here to avoid circular imports
        from agent_cli.agents.factory import create_agent as cli_create_agent
        from agent_cli.agents.llm_provider_factory import create_llm_provider

        # Create execution context
        context = self.create_execution_context(
            session_id=session_id,
            user_id=user_id,
            **kwargs
        )

        workspace_path = context.workspace_path

        logger.info("=" * 60)
        logger.info(f"🔧 [WebAgentFactory] Creating agent")
        logger.info(f"   Agent type: {agent_type}")
        logger.info(f"   Session: {session_id}")
        logger.info(f"   User: {user_id}")
        logger.info(f"   Workspace: {workspace_path}")
        logger.info(f"   Workspace exists: {workspace_path.exists()}")
        logger.info("=" * 60)

        # Log agent creation
        if self.audit_logger:
            self.audit_logger.log_session_event(
                session_id=session_id,
                user_id=user_id,
                event_type="agent_created",
                details={
                    "agent_type": agent_type,
                    "workspace": str(workspace_path),
                    "sandbox_mode": self.sandbox_mode.value,
                    "architecture": "framework",
                }
            )

        # Create LLM provider if not provided
        llm_provider = kwargs.pop("llm_provider", None)
        if llm_provider is None:
            llm_provider = create_llm_provider()

        # Create the base agent using CLI factory
        logger.info(f"📋 [WebAgentFactory] Calling CLI factory with project_directory={workspace_path}")
        agent = cli_create_agent(
            agent_type=agent_type,
            session_id=session_id,
            llm_provider=llm_provider,
            project_directory=str(workspace_path),
            **kwargs
        )
        logger.info(f"✅ [WebAgentFactory] Agent created: {type(agent).__name__}")
        logger.info(f"   Agent has execution_context: {hasattr(agent, 'execution_context')}")
        if hasattr(agent, 'execution_context') and agent.execution_context:
            logger.info(f"   Agent execution_context.working_directory: {agent.execution_context.working_directory}")

        # Setup sandbox with framework SessionRuntimeManager
        await self._setup_agent_sandbox(agent, context)

        # Store context on agent for reference
        agent._web_context = context

        return agent

    def get_agent_tools(self, agent_type: str) -> List[str]:
        """
        Get the list of tools available for an agent type.

        Args:
            agent_type: Type of agent

        Returns:
            List of tool names
        """
        # This maps agent types to their tools
        # Used for UI display and validation
        tool_sets = {
            "coding": [
                "read", "write", "edit", "multi_edit", "glob", "grep",
                "bash", "list", "todo_read", "todo_write"
            ],
            "comic": [
                "read", "write", "glob", "generate_image", "export_pdf"
            ],
            "ppt": [
                "read", "write", "glob", "generate_image", "export_pptx"
            ],
            "research": [
                "read", "write", "glob", "grep", "web_search", "web_fetch"
            ],
            "simple": [
                "read", "write", "glob"
            ],
        }

        return tool_sets.get(agent_type, ["read", "write", "glob"])


# Singleton factory instance (will be configured by app startup)
_factory_instance: Optional[WebAgentFactory] = None


def get_web_agent_factory() -> WebAgentFactory:
    """Get the global WebAgentFactory instance."""
    if _factory_instance is None:
        raise RuntimeError("WebAgentFactory not initialized. Call init_web_agent_factory first.")
    return _factory_instance


def init_web_agent_factory(
    workspace_manager: WorkspaceManager,
    storage_manager: Optional[StorageManager] = None,
    audit_logger: Optional[AuditLogger] = None,
    sandbox_mode: SandboxMode = SandboxMode.STRICT,
) -> WebAgentFactory:
    """
    Initialize the global WebAgentFactory.

    Should be called during application startup.

    Args:
        workspace_manager: Manager for session workspaces
        storage_manager: Optional manager for storage quotas
        audit_logger: Optional logger for audit trail
        sandbox_mode: Sandbox enforcement level

    Returns:
        The initialized factory instance
    """
    global _factory_instance

    _factory_instance = WebAgentFactory(
        workspace_manager=workspace_manager,
        storage_manager=storage_manager,
        audit_logger=audit_logger,
        sandbox_mode=sandbox_mode,
    )

    logger.info(
        f"WebAgentFactory global instance initialized: sandbox_mode={sandbox_mode.value}"
    )

    return _factory_instance
