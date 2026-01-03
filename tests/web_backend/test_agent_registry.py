"""
Tests for AgentRegistry.
"""

import pytest

from src.web_backend.services.agent_registry import (
    AgentRegistry,
    AgentMetadata,
    AgentCapability,
    AgentCategory,
    get_agent_registry,
    DEFAULT_AGENTS,
)


class TestAgentMetadata:
    """Tests for AgentMetadata dataclass."""

    def test_create_metadata(self):
        """Test creating agent metadata."""
        metadata = AgentMetadata(
            type="test",
            name="Test Agent",
            description="A test agent",
            category=AgentCategory.DEVELOPMENT,
            icon="test",
            color="#FF0000",
        )

        assert metadata.type == "test"
        assert metadata.name == "Test Agent"
        assert metadata.category == AgentCategory.DEVELOPMENT

    def test_metadata_to_dict(self):
        """Test converting metadata to dictionary."""
        metadata = AgentMetadata(
            type="test",
            name="Test Agent",
            description="A test agent",
            category=AgentCategory.CREATIVE,
            icon="test",
            color="#FF0000",
            capabilities=[
                AgentCapability("cap1", "Capability 1"),
            ],
            example_prompts=["Example 1"],
            tags=["tag1", "tag2"],
        )

        result = metadata.to_dict()

        assert result["type"] == "test"
        assert result["category"] == "creative"
        assert len(result["capabilities"]) == 1
        assert result["capabilities"][0]["name"] == "cap1"
        assert result["example_prompts"] == ["Example 1"]
        assert result["tags"] == ["tag1", "tag2"]

    def test_metadata_defaults(self):
        """Test metadata default values."""
        metadata = AgentMetadata(
            type="test",
            name="Test",
            description="Test",
            category=AgentCategory.GENERAL,
            icon="default",
            color="#000000",
        )

        assert metadata.capabilities == []
        assert metadata.workflow_type == "chat_heavy"
        assert metadata.supports_streaming is True
        assert metadata.supports_artifacts is True
        assert metadata.supports_workflow is True
        assert metadata.example_prompts == []
        assert metadata.tags == []


class TestAgentRegistry:
    """Tests for AgentRegistry class."""

    @pytest.fixture
    def registry(self):
        """Create a fresh registry."""
        return AgentRegistry()

    def test_default_agents_loaded(self, registry):
        """Test that default agents are loaded."""
        agents = registry.list_all()
        assert len(agents) >= 4

        types = [a.type for a in agents]
        assert "comic" in types
        assert "ppt" in types
        assert "coding" in types
        assert "research" in types

    def test_get_agent(self, registry):
        """Test getting a specific agent."""
        agent = registry.get("comic")

        assert agent is not None
        assert agent.type == "comic"
        assert agent.name == "Comic Creator"
        assert agent.category == AgentCategory.CREATIVE

    def test_get_nonexistent_agent(self, registry):
        """Test getting a nonexistent agent."""
        agent = registry.get("nonexistent")
        assert agent is None

    def test_exists(self, registry):
        """Test existence check."""
        assert registry.exists("comic")
        assert not registry.exists("nonexistent")

    def test_register_new_agent(self, registry):
        """Test registering a new agent."""
        new_agent = AgentMetadata(
            type="custom",
            name="Custom Agent",
            description="A custom agent",
            category=AgentCategory.GENERAL,
            icon="custom",
            color="#123456",
        )

        registry.register(new_agent)

        assert registry.exists("custom")
        assert registry.get("custom") == new_agent

    def test_unregister_agent(self, registry):
        """Test unregistering an agent."""
        assert registry.exists("comic")

        result = registry.unregister("comic")

        assert result is True
        assert not registry.exists("comic")

    def test_unregister_nonexistent(self, registry):
        """Test unregistering a nonexistent agent."""
        result = registry.unregister("nonexistent")
        assert result is False

    def test_list_by_category(self, registry):
        """Test listing agents by category."""
        creative = registry.list_by_category(AgentCategory.CREATIVE)
        types = [a.type for a in creative]

        assert "comic" in types
        assert "ppt" in types
        assert "coding" not in types

    def test_get_categories(self, registry):
        """Test getting category list with counts."""
        categories = registry.get_categories()

        assert len(categories) > 0
        assert all("id" in c for c in categories)
        assert all("name" in c for c in categories)
        assert all("count" in c for c in categories)

        # Check that creative category has at least 2
        creative = next(c for c in categories if c["id"] == "creative")
        assert creative["count"] >= 2

    def test_search_by_name(self, registry):
        """Test searching agents by name."""
        results = registry.search("comic")

        assert len(results) == 1
        assert results[0].type == "comic"

    def test_search_by_description(self, registry):
        """Test searching agents by description."""
        results = registry.search("presentation")

        assert len(results) >= 1
        types = [a.type for a in results]
        assert "ppt" in types

    def test_search_by_tags(self, registry):
        """Test searching agents by tags."""
        results = registry.search("visual")

        # Both comic and ppt have "visual" tag
        types = [a.type for a in results]
        assert "comic" in types or "ppt" in types

    def test_search_case_insensitive(self, registry):
        """Test that search is case insensitive."""
        results1 = registry.search("COMIC")
        results2 = registry.search("comic")

        assert len(results1) == len(results2)

    def test_search_no_results(self, registry):
        """Test search with no results."""
        results = registry.search("xyznonexistent")
        assert len(results) == 0

    def test_get_workflow_definition(self, registry):
        """Test getting workflow definition."""
        workflow = registry.get_workflow_definition("comic")

        assert workflow is not None
        assert workflow["agent_type"] == "comic"
        assert workflow["workflow_type"] == "phase_heavy"
        assert workflow["total_phases"] == 5

    def test_get_workflow_definition_none(self, registry):
        """Test getting workflow for agent without definition."""
        # Register a new agent without workflow
        new_agent = AgentMetadata(
            type="no_workflow",
            name="No Workflow Agent",
            description="Agent without workflow",
            category=AgentCategory.GENERAL,
            icon="none",
            color="#000000",
        )
        registry.register(new_agent)

        workflow = registry.get_workflow_definition("no_workflow")
        assert workflow is None


class TestDefaultAgents:
    """Tests for the default agent configurations."""

    def test_comic_agent_capabilities(self):
        """Test comic agent has expected capabilities."""
        comic = DEFAULT_AGENTS["comic"]

        cap_names = [c.name for c in comic.capabilities]
        assert "script_writing" in cap_names
        assert "panel_generation" in cap_names
        assert "pdf_export" in cap_names

    def test_ppt_agent_capabilities(self):
        """Test PPT agent has expected capabilities."""
        ppt = DEFAULT_AGENTS["ppt"]

        cap_names = [c.name for c in ppt.capabilities]
        assert "outline_creation" in cap_names
        assert "slide_design" in cap_names
        assert "pptx_export" in cap_names

    def test_coding_agent_capabilities(self):
        """Test coding agent has expected capabilities."""
        coding = DEFAULT_AGENTS["coding"]

        cap_names = [c.name for c in coding.capabilities]
        assert "code_writing" in cap_names
        assert "debugging" in cap_names
        assert "testing" in cap_names

    def test_all_agents_have_example_prompts(self):
        """Test all default agents have example prompts."""
        for agent_type, agent in DEFAULT_AGENTS.items():
            assert len(agent.example_prompts) >= 1, f"{agent_type} missing example prompts"

    def test_all_agents_have_tags(self):
        """Test all default agents have tags."""
        for agent_type, agent in DEFAULT_AGENTS.items():
            assert len(agent.tags) >= 1, f"{agent_type} missing tags"

    def test_workflow_type_matches_category(self):
        """Test that workflow types are consistent with categories."""
        # Creative agents should be phase_heavy
        assert DEFAULT_AGENTS["comic"].workflow_type == "phase_heavy"
        assert DEFAULT_AGENTS["ppt"].workflow_type == "phase_heavy"

        # Development/Research agents should be chat_heavy
        assert DEFAULT_AGENTS["coding"].workflow_type == "chat_heavy"
        assert DEFAULT_AGENTS["research"].workflow_type == "chat_heavy"


class TestGetAgentRegistry:
    """Tests for the global registry singleton."""

    def test_singleton(self):
        """Test that get_agent_registry returns the same instance."""
        registry1 = get_agent_registry()
        registry2 = get_agent_registry()

        assert registry1 is registry2
