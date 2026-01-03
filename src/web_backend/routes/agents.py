"""
Agent API routes.

Handles agent metadata and discovery.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

from ..services.agent_registry import get_agent_registry, AgentCategory

router = APIRouter()


class AgentPhase(BaseModel):
    """Information about an agent's workflow phase."""
    id: str
    name: str
    description: Optional[str] = None
    order: int = 0
    requires_approval: bool = False
    artifacts: List[str] = Field(default_factory=list)


class AgentCapability(BaseModel):
    """Information about an agent capability."""
    name: str
    description: str


class AgentInfo(BaseModel):
    """Information about an available agent type."""
    id: str = Field(..., description="Agent type identifier")
    name: str = Field(..., description="Human-readable agent name")
    description: str = Field(..., description="Agent description")
    category: str = Field(..., description="Agent category (creative, development, etc.)")
    icon: str = Field(default="default", description="Icon identifier")
    color: str = Field(default="#6B7280", description="Theme color")
    workflow_type: str = Field(
        ...,
        description="Workflow type: 'phase_heavy' or 'chat_heavy'"
    )
    capabilities: List[AgentCapability] = Field(
        default_factory=list,
        description="Agent capabilities"
    )
    supports_streaming: bool = Field(default=True, description="Whether agent supports streaming")
    supports_artifacts: bool = Field(default=True, description="Whether agent creates artifacts")
    supports_workflow: bool = Field(default=True, description="Whether agent has workflow phases")
    example_prompts: List[str] = Field(default_factory=list, description="Example prompts")
    tags: List[str] = Field(default_factory=list, description="Search tags")


class AgentList(BaseModel):
    """Response schema for listing agents."""
    agents: List[AgentInfo]
    total: int
    categories: List[dict] = Field(default_factory=list, description="Available categories")


class WorkflowDefinition(BaseModel):
    """Workflow definition for an agent type."""
    agent_type: str
    workflow_type: str
    phases: List[AgentPhase]
    total_phases: int


@router.get("/", response_model=AgentList)
async def list_agents(
    category: Optional[str] = Query(None, description="Filter by category"),
    search: Optional[str] = Query(None, description="Search query"),
):
    """
    List all available agent types.

    Returns metadata about each agent including capabilities,
    workflow type, and example prompts.

    Supports filtering by category and searching by name/description/tags.
    """
    registry = get_agent_registry()

    # Get agents based on filters
    if search:
        agents = registry.search(search)
    elif category:
        try:
            cat = AgentCategory(category)
            agents = registry.list_by_category(cat)
        except ValueError:
            agents = []
    else:
        agents = registry.list_all()

    # Convert to response format
    agent_infos = []
    for agent in agents:
        agent_infos.append(AgentInfo(
            id=agent.type,
            name=agent.name,
            description=agent.description,
            category=agent.category.value,
            icon=agent.icon,
            color=agent.color,
            workflow_type=agent.workflow_type,
            capabilities=[
                AgentCapability(name=c.name, description=c.description)
                for c in agent.capabilities
            ],
            supports_streaming=agent.supports_streaming,
            supports_artifacts=agent.supports_artifacts,
            supports_workflow=agent.supports_workflow,
            example_prompts=agent.example_prompts,
            tags=agent.tags,
        ))

    return AgentList(
        agents=agent_infos,
        total=len(agent_infos),
        categories=registry.get_categories(),
    )


@router.get("/categories")
async def list_categories():
    """
    List all agent categories with counts.

    Returns a list of categories and how many agents are in each.
    """
    registry = get_agent_registry()
    return {"categories": registry.get_categories()}


@router.get("/{agent_type}", response_model=AgentInfo)
async def get_agent(agent_type: str):
    """
    Get information about a specific agent type.

    Returns detailed metadata including capabilities and example prompts.
    """
    registry = get_agent_registry()
    agent = registry.get(agent_type)

    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_type}' not found")

    return AgentInfo(
        id=agent.type,
        name=agent.name,
        description=agent.description,
        category=agent.category.value,
        icon=agent.icon,
        color=agent.color,
        workflow_type=agent.workflow_type,
        capabilities=[
            AgentCapability(name=c.name, description=c.description)
            for c in agent.capabilities
        ],
        supports_streaming=agent.supports_streaming,
        supports_artifacts=agent.supports_artifacts,
        supports_workflow=agent.supports_workflow,
        example_prompts=agent.example_prompts,
        tags=agent.tags,
    )


@router.get("/{agent_type}/workflow", response_model=WorkflowDefinition)
async def get_agent_workflow(agent_type: str):
    """
    Get the workflow definition for an agent type.

    Returns the phases, their order, and approval requirements.
    """
    registry = get_agent_registry()

    if not registry.exists(agent_type):
        raise HTTPException(status_code=404, detail=f"Agent '{agent_type}' not found")

    workflow = registry.get_workflow_definition(agent_type)

    if not workflow:
        # Return empty workflow for agents without defined phases
        return WorkflowDefinition(
            agent_type=agent_type,
            workflow_type="chat_heavy",
            phases=[],
            total_phases=0,
        )

    # Convert phases to response format
    phases = [
        AgentPhase(
            id=p["id"],
            name=p["name"],
            description=p.get("description"),
            order=p["order"],
            requires_approval=p.get("requires_approval", False),
            artifacts=p.get("artifacts", []),
        )
        for p in workflow["phases"]
    ]

    return WorkflowDefinition(
        agent_type=agent_type,
        workflow_type=workflow["workflow_type"],
        phases=phases,
        total_phases=workflow["total_phases"],
    )
