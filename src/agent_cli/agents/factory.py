"""
Agent factory for creating different types of agents.

Supports creating:
- CodingAgent for software development tasks
- SimpleAgent for general conversations
- CodebaseAnalyzerAgent for codebase analysis and reporting
- CodeReviewAgent for code review tasks
- ProductManagerAgent for product brainstorming and requirements
- TechLeadAgent for system architecture and technical planning
- PPTAgent for presentation creation
- ResearchAgent for comprehensive research and reporting
- ComicAgent for comic book creation
"""

import os
from typing import Literal

from agent_framework.agents.base import BaseAgent, SimpleAgent
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

# Import the refactored factories
from .llm_provider_factory import create_llm_provider, get_supported_providers
from .agent_factory_impl import create_agent as _create_agent, get_supported_agent_types
from .exceptions import AgentFactoryError

AgentType = Literal["coding", "codingv2", "codingv3", "simple", "simplev2", "analyzer", "reviewer", "product", "architect", "ppt", "research", "prompt_refiner", "comic"]


def create_agent(
    agent_type: AgentType,
    session_id: str | None = None,
    llm_provider: LLMProvider | None = None,
    **kwargs: object,
) -> BaseAgent:
    """
    Create an agent instance.

    Args:
        agent_type: Type of agent to create ("coding", "codingv2", "codingv3", "simple", "analyzer", "reviewer", "product", "architect", "ppt", "research", "prompt_refiner", or "comic")
        session_id: Optional session ID
        llm_provider: Optional LLM provider (creates default if not provided)
        **kwargs: Additional arguments for agent creation

    Returns:
        Agent instance

    Raises:
        AgentFactoryError: If agent type is unsupported or creation fails
    """
    # Delegate to the refactored factory implementation
    return _create_agent(
        agent_type=agent_type,
        session_id=session_id,
        llm_provider=llm_provider,
        **kwargs
    )


def create_coding_agent(
    session_id: str | None = None,
    llm_provider: LLMProvider | None = None,
    project_directory: str | None = None,
    **kwargs: object,
) -> CodingAgent:
    """
    Create a CodingAgent instance.

    Args:
        session_id: Optional session ID
        llm_provider: Optional LLM provider
        project_directory: Root directory of project to work on
        **kwargs: Additional arguments

    Returns:
        CodingAgent instance

    Raises:
        AgentFactoryError: If creation fails

    Note:
        This function is maintained for backward compatibility.
        It delegates to the new factory implementation.
    """
    return _create_agent(
        agent_type="coding",
        session_id=session_id,
        llm_provider=llm_provider,
        project_directory=project_directory,
        **kwargs
    )


def create_coding_agent_v2(
    session_id: str | None = None,
    llm_provider: LLMProvider | None = None,
    project_directory: str | None = None,
    **kwargs: object,
) -> CodingAgentV2:
    """
    Create a CodingAgentV2 instance (Claude Code based).

    Args:
        session_id: Optional session ID
        llm_provider: Optional LLM provider
        project_directory: Root directory of project to work on
        **kwargs: Additional arguments

    Returns:
        CodingAgentV2 instance

    Raises:
        AgentFactoryError: If creation fails
    """
    return _create_agent(
        agent_type="codingv2",
        session_id=session_id,
        llm_provider=llm_provider,
        project_directory=project_directory,
        **kwargs
    )


def create_simple_agent(
    session_id: str | None = None,
    llm_provider: LLMProvider | None = None,
    **kwargs: object,
) -> SimpleAgent:
    """
    Create a SimpleAgent instance.

    Args:
        session_id: Optional session ID
        llm_provider: Optional LLM provider
        **kwargs: Additional arguments

    Returns:
        SimpleAgent instance

    Raises:
        AgentFactoryError: If creation fails

    Note:
        This function is maintained for backward compatibility.
        It delegates to the new factory implementation.
    """
    return _create_agent(
        agent_type="simple",
        session_id=session_id,
        llm_provider=llm_provider,
        **kwargs
    )


def create_analyzer_agent(
    session_id: str | None = None,
    llm_provider: LLMProvider | None = None,
    project_directory: str | None = None,
    report_format: str = "markdown",
    analysis_depth: str = "standard",
    **kwargs: object,
) -> CodebaseAnalyzerAgent:
    """
    Create a CodebaseAnalyzerAgent instance.

    Args:
        session_id: Optional session ID
        llm_provider: Optional LLM provider
        project_directory: Root directory of project to analyze
        report_format: Output format - "markdown" or "json"
        analysis_depth: Analysis thoroughness - "quick", "standard", or "deep"
        **kwargs: Additional arguments

    Returns:
        CodebaseAnalyzerAgent instance

    Raises:
        AgentFactoryError: If creation fails

    Note:
        This function is maintained for backward compatibility.
        It delegates to the new factory implementation.
    """
    return _create_agent(
        agent_type="analyzer",
        session_id=session_id,
        llm_provider=llm_provider,
        project_directory=project_directory,
        report_format=report_format,
        analysis_depth=analysis_depth,
        **kwargs
    )


def create_review_agent(
    session_id: str | None = None,
    llm_provider: LLMProvider | None = None,
    project_directory: str | None = None,
    diff_file: str | None = None,
    pr_description_file: str | None = None,
    review_depth: str = "standard",
    focus_areas: list[str] | None = None,
    **kwargs: object,
) -> CodeReviewAgent:
    """
    Create a CodeReviewAgent instance.

    Args:
        session_id: Optional session ID
        llm_provider: Optional LLM provider
        project_directory: Root directory of project to review
        diff_file: Optional path to diff/patch file
        pr_description_file: Optional path to PR description file
        review_depth: Review thoroughness - "quick", "standard", or "thorough"
        focus_areas: Optional list of focus areas (e.g., ["security", "performance"])
        **kwargs: Additional arguments

    Returns:
        CodeReviewAgent instance

    Raises:
        AgentFactoryError: If creation fails

    Note:
        This function is maintained for backward compatibility.
        It delegates to the new factory implementation.
    """
    return _create_agent(
        agent_type="reviewer",
        session_id=session_id,
        llm_provider=llm_provider,
        project_directory=project_directory,
        diff_file=diff_file,
        pr_description_file=pr_description_file,
        review_depth=review_depth,
        focus_areas=focus_areas,
        **kwargs
    )


def create_product_manager_agent(
    session_id: str | None = None,
    llm_provider: LLMProvider | None = None,
    project_directory: str | None = None,
    **kwargs: object,
) -> ProductManagerAgent:
    """
    Create a ProductManagerAgent instance.

    Args:
        session_id: Optional session ID
        llm_provider: Optional LLM provider
        project_directory: Root directory of project to brainstorm for
        **kwargs: Additional arguments

    Returns:
        ProductManagerAgent instance

    Raises:
        AgentFactoryError: If creation fails

    Note:
        This function is maintained for backward compatibility.
        It delegates to the new factory implementation.
    """
    return _create_agent(
        agent_type="product",
        session_id=session_id,
        llm_provider=llm_provider,
        project_directory=project_directory,
        **kwargs
    )


def create_tech_lead_agent(
    session_id: str | None = None,
    llm_provider: LLMProvider | None = None,
    project_directory: str | None = None,
    **kwargs: object,
) -> TechLeadAgent:
    """
    Create a TechLeadAgent instance.

    Args:
        session_id: Optional session ID
        llm_provider: Optional LLM provider
        project_directory: Root directory of project to architect
        **kwargs: Additional arguments

    Returns:
        TechLeadAgent instance

    Raises:
        AgentFactoryError: If creation fails

    Note:
        This function is maintained for backward compatibility.
        It delegates to the new factory implementation.
    """
    return _create_agent(
        agent_type="architect",
        session_id=session_id,
        llm_provider=llm_provider,
        project_directory=project_directory,
        **kwargs
    )


def create_coding_agent_v3(
    session_id: str | None = None,
    llm_provider: LLMProvider | None = None,
    project_directory: str | None = None,
    **kwargs: object,
) -> CodingAgentV3:
    """
    Create a CodingAgentV3 instance.

    Args:
        session_id: Optional session ID
        llm_provider: Optional LLM provider
        project_directory: Optional project directory for code
        **kwargs: Additional arguments

    Returns:
        CodingAgentV3 instance

    Raises:
        AgentFactoryError: If creation fails
    """
    return _create_agent(
        agent_type="codingv3",
        session_id=session_id,
        llm_provider=llm_provider,
        project_directory=project_directory,
        **kwargs
    )


def create_research_agent(
    session_id: str | None = None,
    llm_provider: LLMProvider | None = None,
    project_directory: str | None = None,
    **kwargs: object,
) -> ResearchAgent:
    """
    Create a ResearchAgent instance.

    Args:
        session_id: Optional session ID
        llm_provider: Optional LLM provider
        project_directory: Optional project directory for saving research
        **kwargs: Additional arguments

    Returns:
        ResearchAgent instance

    Raises:
        AgentFactoryError: If creation fails
    """
    return _create_agent(
        agent_type="research",
        session_id=session_id,
        llm_provider=llm_provider,
        project_directory=project_directory,
        **kwargs
    )


def create_prompt_refiner_agent(
    session_id: str | None = None,
    llm_provider: LLMProvider | None = None,
    initial_prompt: str | None = None,
    **kwargs: object,
) -> BaseAgent:
    """
    Create a PromptRefinerAgent instance.

    Args:
        session_id: Optional session ID
        llm_provider: Optional LLM provider
        initial_prompt: Optional initial prompt to start refinement
        **kwargs: Additional arguments

    Returns:
        PromptRefinerAgent instance

    Raises:
        AgentFactoryError: If creation fails
    """
    return _create_agent(
        agent_type="prompt_refiner",
        session_id=session_id,
        llm_provider=llm_provider,
        initial_prompt=initial_prompt,
        **kwargs
    )


def create_comic_agent(
    session_id: str | None = None,
    llm_provider: LLMProvider | None = None,
    google_api_key: str | None = None,
    project_directory: str | None = None,
    **kwargs: object,
) -> BaseAgent:
    """
    Create a ComicAgent instance for comic book generation.

    Args:
        session_id: Optional session ID
        llm_provider: Optional LLM provider
        google_api_key: Google API key for image generation (or set GOOGLE_API_KEY env var)
        project_directory: Optional project directory for session storage
        **kwargs: Additional arguments

    Returns:
        ComicAgent instance

    Raises:
        AgentFactoryError: If creation fails or GOOGLE_API_KEY is missing
    """
    return _create_agent(
        agent_type="comic",
        session_id=session_id,
        llm_provider=llm_provider,
        google_api_key=google_api_key,
        project_directory=project_directory,
        **kwargs
    )
