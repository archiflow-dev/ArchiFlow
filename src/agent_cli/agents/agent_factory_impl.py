"""
Agent Factory implementation using the Factory Method pattern.

This module provides a cleaner, more extensible way to create agents
without relying on multiple if-elif statements.
"""

import os
import time
from abc import ABC, abstractmethod
from typing import Dict, Type, Callable, Optional, Any

from agent_framework.agents.base import BaseAgent, SimpleAgent
from agent_framework.agents.coding_agent import CodingAgent
from agent_framework.agents.codebase_analyzer_agent import CodebaseAnalyzerAgent
from agent_framework.agents.code_review_agent import CodeReviewAgent
from agent_framework.agents.product_manager_agent import ProductManagerAgent
from agent_framework.agents.tech_lead_agent import TechLeadAgent
from agent_framework.llm.provider import LLMProvider

from .exceptions import AgentFactoryError
from .llm_provider_factory import create_llm_provider


class AgentConfig:
    """Configuration class for agent types."""

    def __init__(
        self,
        agent_class: Type[BaseAgent],
        session_prefix: str,
        requires_project_dir: bool = False,
        default_debug_log_name: Optional[str] = None,
        creator_func: Optional[Callable] = None
    ):
        self.agent_class = agent_class
        self.session_prefix = session_prefix
        self.requires_project_dir = requires_project_dir
        self.default_debug_log_name = default_debug_log_name
        self.creator_func = creator_func


class AgentFactory:
    """
    Factory for creating agents using the Factory Method pattern.

    This class maintains a registry of agent configurations and creates
    agents based on the requested type.
    """

    def __init__(self):
        self._agents: Dict[str, AgentConfig] = {}
        self._register_agents()

    def _register_agents(self):
        """Register all available agent types."""
        # Register SimpleAgent
        self.register_agent(
            name="simple",
            agent_class=SimpleAgent,
            session_prefix="simple",
            requires_project_dir=False
        )

        # Register CodingAgent
        self.register_agent(
            name="coding",
            agent_class=CodingAgent,
            session_prefix="coding",
            requires_project_dir=True,
            default_debug_log_name="coding_agent.log",
            creator_func=self._create_coding_agent
        )

        # Register CodebaseAnalyzerAgent
        self.register_agent(
            name="analyzer",
            agent_class=CodebaseAnalyzerAgent,
            session_prefix="analyzer",
            requires_project_dir=True,
            default_debug_log_name="analyzer_agent.log",
            creator_func=self._create_analyzer_agent
        )

        # Register CodeReviewAgent
        self.register_agent(
            name="reviewer",
            agent_class=CodeReviewAgent,
            session_prefix="reviewer",
            requires_project_dir=True,
            default_debug_log_name="review_agent.log",
            creator_func=self._create_review_agent
        )

        # Register ProductManagerAgent
        self.register_agent(
            name="product",
            agent_class=ProductManagerAgent,
            session_prefix="product",
            requires_project_dir=True,
            default_debug_log_name="product_agent.log",
            creator_func=self._create_product_manager_agent
        )

        # Register TechLeadAgent
        self.register_agent(
            name="architect",
            agent_class=TechLeadAgent,
            session_prefix="architect",
            requires_project_dir=True,
            default_debug_log_name="architect_agent.log",
            creator_func=self._create_tech_lead_agent
        )

    def register_agent(
        self,
        name: str,
        agent_class: Type[BaseAgent],
        session_prefix: str,
        requires_project_dir: bool = False,
        default_debug_log_name: Optional[str] = None,
        creator_func: Optional[Callable] = None
    ):
        """
        Register a new agent type.

        Args:
            name: Agent type name (e.g., "coding", "simple")
            agent_class: The agent class
            session_prefix: Prefix for auto-generated session IDs
            requires_project_dir: Whether agent requires a project directory
            default_debug_log_name: Default debug log file name
            creator_func: Optional custom creation function
        """
        self._agents[name] = AgentConfig(
            agent_class=agent_class,
            session_prefix=session_prefix,
            requires_project_dir=requires_project_dir,
            default_debug_log_name=default_debug_log_name,
            creator_func=creator_func
        )

    def create_agent(
        self,
        agent_type: str,
        session_id: str | None = None,
        llm_provider: LLMProvider | None = None,
        **kwargs: Any,
    ) -> BaseAgent:
        """
        Create an agent instance.

        Args:
            agent_type: Type of agent to create
            session_id: Optional session ID
            llm_provider: Optional LLM provider (creates default if not provided)
            **kwargs: Additional arguments for agent creation

        Returns:
            Agent instance

        Raises:
            AgentFactoryError: If agent type is unsupported or creation fails
        """
        # Validate agent type
        if agent_type not in self._agents:
            supported = ", ".join(self._agents.keys())
            raise AgentFactoryError(
                f"Unknown agent type: {agent_type}. "
                f"Supported types: {supported}"
            )

        config = self._agents[agent_type]

        # Create LLM provider if not provided
        if llm_provider is None:
            try:
                llm_provider = create_llm_provider()
            except AgentFactoryError as e:
                # Re-raise with more context
                raise AgentFactoryError(
                    f"Failed to create {agent_type} agent: LLM provider initialization failed. "
                    "Make sure appropriate API key is set."
                ) from e

        # Generate session_id if not provided
        if session_id is None:
            session_id = f"{config.session_prefix}_{int(time.time())}"

        # Handle project directory for agents that require it
        if config.requires_project_dir and "project_directory" not in kwargs:
            kwargs["project_directory"] = os.getcwd()

        # Set debug log path if not provided and default exists
        if (config.default_debug_log_name and "debug_log_path" not in kwargs
                and "project_directory" in kwargs):
            kwargs["debug_log_path"] = f"{kwargs['project_directory']}/logs/debug/{config.default_debug_log_name}"

        # Use custom creator function if available
        if config.creator_func:
            return config.creator_func(
                session_id=session_id,
                llm_provider=llm_provider,
                **kwargs
            )

        # Default creation logic
        try:
            # Special handling for SimpleAgent which uses different parameter order
            if config.agent_class == SimpleAgent:
                # Filter out project_directory since SimpleAgent doesn't use it
                filtered_kwargs = {k: v for k, v in kwargs.items() if k != 'project_directory'}
                agent = config.agent_class(session_id=session_id, llm=llm_provider, **filtered_kwargs)
            else:
                # Most agents expect: session_id, llm (or llm_provider), **kwargs
                # Check if the class has a parameter named 'llm' or 'llm_provider'
                import inspect
                sig = inspect.signature(config.agent_class.__init__)
                if 'llm_provider' in sig.parameters:
                    agent = config.agent_class(
                        session_id=session_id,
                        llm_provider=llm_provider,
                        **kwargs
                    )
                else:
                    agent = config.agent_class(
                        session_id=session_id,
                        llm=llm_provider,
                        **kwargs
                    )

            # Set execution context on all tools for agents that have them
            if hasattr(agent, 'tools') and hasattr(agent, 'execution_context'):
                for tool in agent.tools.list_tools():
                    tool.execution_context = agent.execution_context

            return agent

        except Exception as e:
            raise AgentFactoryError(f"Failed to create {agent_type} agent: {e}") from e

    def get_supported_agent_types(self) -> list[str]:
        """Get list of supported agent type names."""
        return list(self._agents.keys())

    def get_agent_info(self, agent_type: str) -> Dict[str, Any]:
        """
        Get information about an agent type.

        Args:
            agent_type: Name of the agent type

        Returns:
            Dictionary with agent information
        """
        if agent_type not in self._agents:
            raise AgentFactoryError(f"Unknown agent type: {agent_type}")

        config = self._agents[agent_type]
        return {
            "name": agent_type,
            "class": config.agent_class.__name__,
            "session_prefix": config.session_prefix,
            "requires_project_dir": config.requires_project_dir,
            "debug_log_name": config.default_debug_log_name
        }

    # Custom creator functions for complex agents
    def _create_coding_agent(self, session_id, llm_provider, **kwargs) -> CodingAgent:
        """Create a CodingAgent with proper configuration."""
        agent = CodingAgent(
            llm=llm_provider,
            session_id=session_id,
            **kwargs
        )

        # Set execution context on all tools
        for tool in agent.tools.list_tools():
            tool.execution_context = agent.execution_context

        return agent

    def _create_analyzer_agent(self, session_id, llm_provider, **kwargs) -> CodebaseAnalyzerAgent:
        """Create a CodebaseAnalyzerAgent with proper configuration."""
        # Set defaults
        if "report_format" not in kwargs:
            kwargs["report_format"] = "markdown"
        if "analysis_depth" not in kwargs:
            kwargs["analysis_depth"] = "standard"

        agent = CodebaseAnalyzerAgent(
            llm=llm_provider,
            session_id=session_id,
            **kwargs
        )

        # Set execution context on all tools
        for tool in agent.tools.list_tools():
            tool.execution_context = agent.execution_context

        return agent

    def _create_review_agent(self, session_id, llm_provider, **kwargs) -> CodeReviewAgent:
        """Create a CodeReviewAgent with proper configuration."""
        # Set defaults
        if "review_depth" not in kwargs:
            kwargs["review_depth"] = "standard"

        agent = CodeReviewAgent(
            llm=llm_provider,
            session_id=session_id,
            **kwargs
        )

        # Set execution context on all tools
        for tool in agent.tools.list_tools():
            tool.execution_context = agent.execution_context

        return agent

    def _create_product_manager_agent(self, session_id, llm_provider, **kwargs) -> ProductManagerAgent:
        """Create a ProductManagerAgent with proper configuration."""
        agent = ProductManagerAgent(
            llm=llm_provider,
            session_id=session_id,
            **kwargs
        )

        # Set execution context on all tools
        for tool in agent.tools.list_tools():
            tool.execution_context = agent.execution_context

        return agent

    def _create_tech_lead_agent(self, session_id, llm_provider, **kwargs) -> TechLeadAgent:
        """Create a TechLeadAgent with proper configuration."""
        agent = TechLeadAgent(
            llm=llm_provider,
            session_id=session_id,
            **kwargs
        )

        # Set execution context on all tools
        for tool in agent.tools.list_tools():
            tool.execution_context = agent.execution_context

        return agent


# Global factory instance
_agent_factory = AgentFactory()


def create_agent(
    agent_type: str,
    session_id: str | None = None,
    llm_provider: LLMProvider | None = None,
    **kwargs: Any,
) -> BaseAgent:
    """
    Create an agent instance.

    This is a convenience function that delegates to the global factory.

    Args:
        agent_type: Type of agent to create
        session_id: Optional session ID
        llm_provider: Optional LLM provider (creates default if not provided)
        **kwargs: Additional arguments for agent creation

    Returns:
        Agent instance
    """
    return _agent_factory.create_agent(
        agent_type=agent_type,
        session_id=session_id,
        llm_provider=llm_provider,
        **kwargs
    )


def get_supported_agent_types() -> list[str]:
    """Get list of supported agent type names."""
    return _agent_factory.get_supported_agent_types()