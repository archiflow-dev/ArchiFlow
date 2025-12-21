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
from agent_framework.agents.simple_agent_v2 import SimpleAgent as SimpleAgentV2
from agent_framework.agents.coding_agent import CodingAgent
from agent_framework.agents.coding_agent_v2 import CodingAgentV2
from agent_framework.agents.codebase_analyzer_agent import CodebaseAnalyzerAgent
from agent_framework.agents.code_review_agent import CodeReviewAgent
from agent_framework.agents.product_manager_agent import ProductManagerAgent
from agent_framework.agents.tech_lead_agent import TechLeadAgent
from agent_framework.agents.ppt_agent import PPTAgent
from agent_framework.agents.research_agent import ResearchAgent
from agent_framework.agents.coding_agent_v3 import CodingAgentV3
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
        # Register SimpleAgent (original)
        self.register_agent(
            name="simple",
            agent_class=SimpleAgent,
            session_prefix="simple",
            requires_project_dir=False,
            creator_func=self._create_simple_agent
        )

        # Register SimpleAgent v2 (enhanced with profiles)
        self.register_agent(
            name="simplev2",
            agent_class=SimpleAgentV2,
            session_prefix="simplev2",
            requires_project_dir=False,
            creator_func=self._create_simple_agent_v2
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

        # Register CodingAgentV2 (Claude Code based)
        self.register_agent(
            name="codingv2",
            agent_class=CodingAgentV2,
            session_prefix="codingv2",
            requires_project_dir=True,
            default_debug_log_name="coding_agent_v2.log",
            creator_func=self._create_coding_agent_v2
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

        # Register PPTAgent
        self.register_agent(
            name="ppt",
            agent_class=PPTAgent,
            session_prefix="ppt",
            requires_project_dir=True,
            default_debug_log_name="ppt_agent.log",
            creator_func=self._create_ppt_agent
        )

        # Register ResearchAgent
        self.register_agent(
            name="research",
            agent_class=ResearchAgent,
            session_prefix="research",
            requires_project_dir=True,
            default_debug_log_name="research_agent.log",
            creator_func=self._create_research_agent
        )

        # Register CodingAgentV3
        self.register_agent(
            name="codingv3",
            agent_class=CodingAgentV3,
            session_prefix="codingv3",
            requires_project_dir=True,
            default_debug_log_name="coding_agent_v3.log",
            creator_func=self._create_coding_agent_v3
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

        # Default creation logic (only when no creator_func is provided)
        else:
            try:
                # Special handling for SimpleAgent which uses different parameter order
                # This only applies when there's no custom creator_func
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

    def _create_coding_agent_v2(self, session_id, llm_provider, **kwargs) -> CodingAgentV2:
        """Create a CodingAgentV2 (Claude Code based) with proper configuration."""
        agent = CodingAgentV2(
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

    def _create_simple_agent_v2(self, session_id, llm_provider, **kwargs) -> SimpleAgentV2:
        """Create a SimpleAgent v2 with profile configuration."""
        # Extract profile from kwargs
        profile = kwargs.pop("profile", "general")
        custom_prompt = kwargs.pop("custom_prompt", None)

        agent = SimpleAgentV2(
            session_id=session_id,
            llm=llm_provider,
            profile=profile,
            custom_prompt=custom_prompt,
            **kwargs
        )

        # Set execution context on all tools if available
        if hasattr(agent, 'execution_context'):
            for tool in agent.tools.list_tools():
                tool.execution_context = agent.execution_context

        return agent

    def _create_ppt_agent(self, session_id, llm_provider, **kwargs) -> PPTAgent:
        """Create a PPTAgent with proper configuration."""
        import os

        # Get Google API key from environment
        google_api_key = os.getenv("GOOGLE_API_KEY")
        if not google_api_key:
            raise AgentFactoryError(
                "GOOGLE_API_KEY environment variable is required for PPT Agent. "
                "Please set it to use image generation features."
            )

        # Set project directory if not provided
        if "project_directory" not in kwargs:
            kwargs["project_directory"] = os.getcwd()

        agent = PPTAgent(
            session_id=session_id,
            llm=llm_provider,
            google_api_key=google_api_key,
            **kwargs
        )

        # Set execution context on all tools if available
        if hasattr(agent, 'execution_context'):
            for tool in agent.tools.list_tools():
                tool.execution_context = agent.execution_context

        return agent

    def _create_research_agent(self, session_id, llm_provider, **kwargs) -> ResearchAgent:
        """Create a ResearchAgent with proper configuration."""
        agent = ResearchAgent(
            session_id=session_id,
            llm=llm_provider,
            **kwargs
        )

        # Set execution context on all tools if available
        if hasattr(agent, 'execution_context'):
            for tool in agent.tools.list_tools():
                tool.execution_context = agent.execution_context

        return agent

    def _create_coding_agent_v3(self, session_id, llm_provider, **kwargs) -> CodingAgentV3:
        """Create a CodingAgentV3 with proper configuration."""
        agent = CodingAgentV3(
            session_id=session_id,
            llm=llm_provider,
            **kwargs
        )

        # Set execution context on all tools if available
        if hasattr(agent, 'execution_context'):
            for tool in agent.tools.list_tools():
                tool.execution_context = agent.execution_context

        return agent

    def _create_simple_agent(self, session_id, llm_provider, **kwargs) -> SimpleAgent:
        """Create a SimpleAgent with finish_task tool."""
        # Create a ToolRegistry and register essential tools including finish_task
        from agent_framework.tools.all_tools import register_all_tools
        from agent_framework.tools.tool_base import ToolRegistry

        # Register all tools and get the populated global registry
        register_all_tools()
        from agent_framework.tools.tool_base import registry
        tools_registry = registry

        # Always set the enhanced system prompt
        enhanced_prompt = """You are a helpful assistant with access to various tools.

IMPORTANT: When you have completed the user's request, you MUST call the finish_task tool
with the reason for completion. This signals that you are done and the task is complete.

If a tool fails or returns insufficient information:
1. Do your best with what you have or with your general knowledge
2. Explain the limitations to the user
3. Then call finish_task

Don't keep trying the same tool repeatedly if it's clearly not working."""

        # Override any existing system_prompt
        kwargs['system_prompt'] = enhanced_prompt

        agent = SimpleAgent(
            session_id=session_id,
            llm=llm_provider,
            tools=tools_registry,
            **kwargs
        )

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