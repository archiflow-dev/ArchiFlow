"""
Agent Registry for ArchiFlow Web Backend.

Provides dynamic discovery and metadata for available agent types.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum
import logging

from .workflow_controller import WORKFLOW_DEFINITIONS, get_workflow_type

logger = logging.getLogger(__name__)


class AgentCategory(str, Enum):
    """Categories of agents."""
    CREATIVE = "creative"
    DEVELOPMENT = "development"
    RESEARCH = "research"
    GENERAL = "general"


@dataclass
class AgentCapability:
    """Describes a capability of an agent."""
    name: str
    description: str


@dataclass
class AgentMetadata:
    """
    Metadata describing an agent type.

    This provides all information needed by the frontend to:
    - Display agent in catalog
    - Show appropriate UI elements
    - Understand agent capabilities
    """
    type: str
    name: str
    description: str
    category: AgentCategory
    icon: str  # Icon identifier for frontend
    color: str  # Theme color (hex or CSS color)
    capabilities: List[AgentCapability] = field(default_factory=list)
    workflow_type: str = "chat_heavy"  # "phase_heavy" or "chat_heavy"
    supports_streaming: bool = True
    supports_artifacts: bool = True
    supports_workflow: bool = True
    example_prompts: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "type": self.type,
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "icon": self.icon,
            "color": self.color,
            "capabilities": [asdict(c) for c in self.capabilities],
            "workflow_type": self.workflow_type,
            "supports_streaming": self.supports_streaming,
            "supports_artifacts": self.supports_artifacts,
            "supports_workflow": self.supports_workflow,
            "example_prompts": self.example_prompts,
            "tags": self.tags,
        }


# Default agent definitions
DEFAULT_AGENTS: Dict[str, AgentMetadata] = {
    "comic": AgentMetadata(
        type="comic",
        name="Comic Creator",
        description="Creates comic books from story prompts with AI-generated panels and dialogue",
        category=AgentCategory.CREATIVE,
        icon="comic",
        color="#8B5CF6",  # Purple
        capabilities=[
            AgentCapability("script_writing", "Generates comic scripts with dialogue and panel descriptions"),
            AgentCapability("visual_spec", "Creates detailed visual specifications for each panel"),
            AgentCapability("character_design", "Generates consistent character reference images"),
            AgentCapability("panel_generation", "Creates comic panels using AI image generation"),
            AgentCapability("pdf_export", "Exports final comic to PDF format"),
        ],
        workflow_type="phase_heavy",
        supports_streaming=True,
        supports_artifacts=True,
        supports_workflow=True,
        example_prompts=[
            "Create a 4-panel comic about a robot learning to cook",
            "Make a superhero comic about a cat with laser eyes",
            "Design a manga-style comic about time travel",
        ],
        tags=["creative", "visual", "storytelling", "ai-art"],
    ),
    "ppt": AgentMetadata(
        type="ppt",
        name="Presentation Designer",
        description="Creates professional PowerPoint presentations with AI-generated visuals",
        category=AgentCategory.CREATIVE,
        icon="presentation",
        color="#F59E0B",  # Amber
        capabilities=[
            AgentCapability("outline_creation", "Creates structured presentation outlines"),
            AgentCapability("slide_design", "Designs individual slides with layout and content"),
            AgentCapability("visual_generation", "Generates images and graphics for slides"),
            AgentCapability("pptx_export", "Exports to PowerPoint format"),
        ],
        workflow_type="phase_heavy",
        supports_streaming=True,
        supports_artifacts=True,
        supports_workflow=True,
        example_prompts=[
            "Create a 10-slide presentation about renewable energy",
            "Design a pitch deck for a startup app idea",
            "Make a presentation about the history of space exploration",
        ],
        tags=["creative", "business", "visual", "presentations"],
    ),
    "coding": AgentMetadata(
        type="coding",
        name="Coding Assistant",
        description="Helps write, review, and debug code across multiple languages",
        category=AgentCategory.DEVELOPMENT,
        icon="code",
        color="#10B981",  # Emerald
        capabilities=[
            AgentCapability("code_writing", "Writes code in multiple programming languages"),
            AgentCapability("code_review", "Reviews code for bugs, style, and best practices"),
            AgentCapability("debugging", "Helps identify and fix bugs in code"),
            AgentCapability("refactoring", "Suggests and implements code improvements"),
            AgentCapability("testing", "Writes and runs tests for code"),
        ],
        workflow_type="chat_heavy",
        supports_streaming=True,
        supports_artifacts=True,
        supports_workflow=True,
        example_prompts=[
            "Help me build a REST API in Python with FastAPI",
            "Review this React component for performance issues",
            "Debug why my async function is not awaiting properly",
        ],
        tags=["development", "coding", "debugging", "review"],
    ),
    "research": AgentMetadata(
        type="research",
        name="Research Assistant",
        description="Conducts research and synthesizes information from multiple sources",
        category=AgentCategory.RESEARCH,
        icon="search",
        color="#3B82F6",  # Blue
        capabilities=[
            AgentCapability("web_search", "Searches the web for relevant information"),
            AgentCapability("synthesis", "Synthesizes information into coherent reports"),
            AgentCapability("citation", "Provides sources and citations for findings"),
            AgentCapability("summarization", "Summarizes long documents and articles"),
        ],
        workflow_type="chat_heavy",
        supports_streaming=True,
        supports_artifacts=True,
        supports_workflow=True,
        example_prompts=[
            "Research the latest developments in quantum computing",
            "Find and summarize studies on remote work productivity",
            "Compare different cloud providers for a startup",
        ],
        tags=["research", "analysis", "information", "reports"],
    ),
}


class AgentRegistry:
    """
    Registry for discovering and managing agent types.

    Provides:
    - Agent metadata lookup
    - Category-based filtering
    - Workflow definition access
    - Dynamic agent registration
    """

    def __init__(self):
        """Initialize the registry with default agents."""
        self._agents: Dict[str, AgentMetadata] = DEFAULT_AGENTS.copy()

    def register(self, agent: AgentMetadata) -> None:
        """
        Register a new agent type.

        Args:
            agent: Agent metadata to register
        """
        self._agents[agent.type] = agent
        logger.info(f"Registered agent type: {agent.type}")

    def unregister(self, agent_type: str) -> bool:
        """
        Unregister an agent type.

        Args:
            agent_type: Type to unregister

        Returns:
            True if unregistered, False if not found
        """
        if agent_type in self._agents:
            del self._agents[agent_type]
            logger.info(f"Unregistered agent type: {agent_type}")
            return True
        return False

    def get(self, agent_type: str) -> Optional[AgentMetadata]:
        """
        Get metadata for an agent type.

        Args:
            agent_type: Agent type identifier

        Returns:
            AgentMetadata or None if not found
        """
        return self._agents.get(agent_type)

    def list_all(self) -> List[AgentMetadata]:
        """
        List all registered agents.

        Returns:
            List of all agent metadata
        """
        return list(self._agents.values())

    def list_by_category(self, category: AgentCategory) -> List[AgentMetadata]:
        """
        List agents in a specific category.

        Args:
            category: Category to filter by

        Returns:
            List of agents in the category
        """
        return [a for a in self._agents.values() if a.category == category]

    def get_categories(self) -> List[dict]:
        """
        Get list of categories with agent counts.

        Returns:
            List of category info dicts
        """
        category_counts = {}
        for agent in self._agents.values():
            cat = agent.category.value
            if cat not in category_counts:
                category_counts[cat] = {"id": cat, "name": cat.title(), "count": 0}
            category_counts[cat]["count"] += 1

        return list(category_counts.values())

    def get_workflow_definition(self, agent_type: str) -> Optional[dict]:
        """
        Get workflow definition for an agent type.

        Args:
            agent_type: Agent type identifier

        Returns:
            Workflow definition dict or None
        """
        phases = WORKFLOW_DEFINITIONS.get(agent_type)
        if not phases:
            return None

        return {
            "agent_type": agent_type,
            "workflow_type": get_workflow_type(agent_type),
            "phases": phases,
            "total_phases": len(phases),
        }

    def search(self, query: str) -> List[AgentMetadata]:
        """
        Search agents by name, description, or tags.

        Args:
            query: Search query

        Returns:
            List of matching agents
        """
        query = query.lower()
        results = []

        for agent in self._agents.values():
            if (
                query in agent.name.lower()
                or query in agent.description.lower()
                or any(query in tag.lower() for tag in agent.tags)
            ):
                results.append(agent)

        return results

    def exists(self, agent_type: str) -> bool:
        """Check if an agent type exists."""
        return agent_type in self._agents


# Global singleton instance
_agent_registry: Optional[AgentRegistry] = None


def get_agent_registry() -> AgentRegistry:
    """Get the global AgentRegistry instance."""
    global _agent_registry
    if _agent_registry is None:
        _agent_registry = AgentRegistry()
    return _agent_registry
