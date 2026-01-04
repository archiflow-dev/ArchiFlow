"""
Web Agent Factory for ArchiFlow Web Backend.

Creates agents with sandboxed tools for secure web execution.
This implements Option C: Handle tool wrapping at agent creation time.
"""

from typing import Optional, List, Dict, Any, TYPE_CHECKING
from pathlib import Path
import logging
import copy

from agent_framework.tools.tool_base import BaseTool, ToolResult
from agent_framework.runtime.context import ExecutionContext

from .web_context import WebExecutionContext, SandboxMode
from .sandboxed_tool import SandboxedToolWrapper, SandboxedToolkit
from .workspace_manager import WorkspaceManager
from .storage_manager import StorageManager
from .audit_logger import AuditLogger

if TYPE_CHECKING:
    from agent_framework.agents.base import BaseAgent

logger = logging.getLogger(__name__)


class WebAgentFactory:
    """
    Factory for creating agents with sandbox-wrapped tools.

    This factory creates agents configured for secure web execution:
    - All file tools are wrapped with SandboxedToolWrapper
    - Paths are validated against the session workspace
    - Storage quotas are enforced
    - All operations are audit logged

    Usage:
        factory = WebAgentFactory(
            workspace_manager=workspace_manager,
            storage_manager=storage_manager,
            audit_logger=audit_logger
        )

        agent = await factory.create_agent(
            agent_type="coding",
            session_id="session_123",
            user_id="user_456",
            user_prompt="Build a web app"
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

    def wrap_tools(
        self,
        tools: List[BaseTool],
        context: WebExecutionContext
    ) -> SandboxedToolkit:
        """
        Wrap a list of tools with sandbox enforcement.

        Args:
            tools: List of tools to wrap
            context: Execution context for sandbox configuration

        Returns:
            SandboxedToolkit containing wrapped tools
        """
        return SandboxedToolkit(tools, context)

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
                }
            )

        # Create LLM provider if not provided
        llm_provider = kwargs.pop("llm_provider", None)
        if llm_provider is None:
            llm_provider = create_llm_provider()

        # Create the base agent using CLI factory
        # Note: We pass workspace as project_directory for agents that need it
        agent = cli_create_agent(
            agent_type=agent_type,
            session_id=session_id,
            llm_provider=llm_provider,
            project_directory=str(workspace_path),
            **kwargs
        )

        # Set execution context on all tools
        if hasattr(agent, 'tools') and agent.tools:
            # Wrap tools with sandbox
            toolkit = self.wrap_tools(agent.tools, context)

            # Replace agent's tools with sandboxed versions
            sandboxed_tools = toolkit.get_all()

            # Store original tools for reference
            agent._original_tools = agent.tools

            # Replace with sandboxed tools (maintain same list reference if possible)
            agent.tools = sandboxed_tools

            # CRITICAL: Also update tool_registry to use sandboxed tools
            # The RuntimeExecutor uses tool_registry.get() to find tools,
            # so we must ensure it returns sandboxed versions
            # We use the toolkit's non-singleton registry instead of the
            # global ToolRegistry to ensure per-session isolation
            if hasattr(agent, 'tool_registry'):
                agent.tool_registry = toolkit.get_registry()

            logger.info(
                f"Created {agent_type} agent with {len(sandboxed_tools)} sandboxed tools "
                f"for session {session_id}"
            )

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

    logger.info(f"WebAgentFactory initialized with sandbox_mode={sandbox_mode.value}")

    return _factory_instance
