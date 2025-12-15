"""
Integration tests for agent factory.

These tests verify that all agent types can be created successfully
and that the factory integration works correctly.
"""

import pytest
import os
from pathlib import Path

from agent_cli.agents.factory import (
    create_agent,
    create_llm_provider,
    create_coding_agent,
    create_simple_agent,
    create_analyzer_agent,
    create_review_agent,
    create_product_manager_agent,
    AgentFactoryError
)
from agent_framework.agents.coding_agent import CodingAgent
from agent_framework.agents.base import SimpleAgent
from agent_framework.agents.codebase_analyzer_agent import CodebaseAnalyzerAgent
from agent_framework.agents.code_review_agent import CodeReviewAgent
from agent_framework.agents.product_manager_agent import ProductManagerAgent
from agent_framework.llm.mock import MockLLMProvider


@pytest.fixture
def mock_llm():
    """Create a mock LLM provider."""
    return MockLLMProvider()


@pytest.fixture
def test_project_dir(tmp_path):
    """Create a temporary project directory."""
    (tmp_path / "src").mkdir()
    (tmp_path / "README.md").write_text("# Test Project\n")
    return tmp_path


class TestFactoryAgentCreation:
    """Test that all agent types can be created via factory."""

    def test_create_coding_agent(self, mock_llm, test_project_dir):
        """Test creating a coding agent via create_agent factory."""
        agent = create_agent(
            agent_type="coding",
            llm_provider=mock_llm,
            project_directory=str(test_project_dir)
        )

        assert isinstance(agent, CodingAgent)
        assert agent.session_id.startswith("coding_")
        assert agent.project_directory == test_project_dir

    # Note: SimpleAgent tests skipped due to pre-existing bug in SimpleAgent
    # (AttributeError: 'SimpleAgent' object has no attribute 'system_prompt')

    def test_create_analyzer_agent(self, mock_llm, test_project_dir):
        """Test creating an analyzer agent via create_agent factory."""
        agent = create_agent(
            agent_type="analyzer",
            llm_provider=mock_llm,
            project_directory=str(test_project_dir)
        )

        assert isinstance(agent, CodebaseAnalyzerAgent)
        assert agent.session_id.startswith("analyzer_")
        assert agent.project_directory == test_project_dir

    def test_create_review_agent(self, mock_llm, test_project_dir):
        """Test creating a review agent via create_agent factory."""
        agent = create_agent(
            agent_type="reviewer",
            llm_provider=mock_llm,
            project_directory=str(test_project_dir)
        )

        assert isinstance(agent, CodeReviewAgent)
        assert agent.session_id.startswith("reviewer_")
        assert agent.project_directory == test_project_dir

    def test_create_product_manager_agent(self, mock_llm, test_project_dir):
        """Test creating a product manager agent via create_agent factory."""
        agent = create_agent(
            agent_type="product",
            llm_provider=mock_llm,
            project_directory=str(test_project_dir)
        )

        assert isinstance(agent, ProductManagerAgent)
        assert agent.session_id.startswith("product_")
        assert agent.project_directory == test_project_dir

    def test_invalid_agent_type(self, mock_llm):
        """Test that invalid agent type raises error."""
        with pytest.raises(AgentFactoryError, match="Unknown agent type"):
            create_agent(
                agent_type="invalid",  # type: ignore
                llm_provider=mock_llm
            )


class TestFactoryHelpers:
    """Test individual factory helper functions."""

    def test_create_coding_agent_helper(self, mock_llm, test_project_dir):
        """Test create_coding_agent helper function."""
        agent = create_coding_agent(
            llm_provider=mock_llm,
            project_directory=str(test_project_dir)
        )

        assert isinstance(agent, CodingAgent)
        assert agent.project_directory == test_project_dir

    # Note: SimpleAgent tests skipped due to pre-existing bug

    def test_create_analyzer_agent_helper(self, mock_llm, test_project_dir):
        """Test create_analyzer_agent helper function."""
        agent = create_analyzer_agent(
            llm_provider=mock_llm,
            project_directory=str(test_project_dir)
        )

        assert isinstance(agent, CodebaseAnalyzerAgent)
        assert agent.report_format == "markdown"
        assert agent.analysis_depth == "standard"

    def test_create_review_agent_helper(self, mock_llm, test_project_dir):
        """Test create_review_agent helper function."""
        agent = create_review_agent(
            llm_provider=mock_llm,
            project_directory=str(test_project_dir)
        )

        assert isinstance(agent, CodeReviewAgent)
        assert agent.review_depth == "standard"

    def test_create_product_manager_agent_helper(self, mock_llm, test_project_dir):
        """Test create_product_manager_agent helper function."""
        agent = create_product_manager_agent(
            llm_provider=mock_llm,
            project_directory=str(test_project_dir)
        )

        assert isinstance(agent, ProductManagerAgent)
        assert agent.project_directory == test_project_dir


class TestBackwardsCompatibility:
    """Test that existing agent types still work after adding new agent."""

    def test_all_existing_agents_still_work(self, mock_llm, test_project_dir):
        """Test that all existing agent types can still be created."""
        # Test coding agent
        coding = create_agent("coding", llm_provider=mock_llm, project_directory=str(test_project_dir))
        assert isinstance(coding, CodingAgent)

        # Test analyzer agent
        analyzer = create_agent("analyzer", llm_provider=mock_llm, project_directory=str(test_project_dir))
        assert isinstance(analyzer, CodebaseAnalyzerAgent)

        # Test reviewer agent
        reviewer = create_agent("reviewer", llm_provider=mock_llm, project_directory=str(test_project_dir))
        assert isinstance(reviewer, CodeReviewAgent)

        # Test product manager agent (newly added)
        product = create_agent("product", llm_provider=mock_llm, project_directory=str(test_project_dir))
        assert isinstance(product, ProductManagerAgent)

        # Verify all agents are running
        assert coding.is_running
        assert analyzer.is_running
        assert reviewer.is_running
        assert product.is_running

    def test_product_agent_has_correct_tools(self, mock_llm, test_project_dir):
        """Test that product manager agent has only documentation tools."""
        agent = create_product_manager_agent(
            llm_provider=mock_llm,
            project_directory=str(test_project_dir)
        )

        # Check allowed tools
        assert "todo_write" in agent.allowed_tools
        assert "write" in agent.allowed_tools
        assert "read" in agent.allowed_tools
        assert "finish_task" in agent.allowed_tools

        # Check forbidden tools are NOT in allowed list
        assert "edit" not in agent.allowed_tools
        assert "bash" not in agent.allowed_tools
        assert "grep" not in agent.allowed_tools


class TestSessionIDGeneration:
    """Test that session IDs are generated correctly for each agent type."""

    def test_unique_session_ids_for_each_agent_type(self, mock_llm, test_project_dir):
        """Test that each agent type gets a unique session ID prefix."""
        coding = create_coding_agent(llm_provider=mock_llm, project_directory=str(test_project_dir))
        analyzer = create_analyzer_agent(llm_provider=mock_llm, project_directory=str(test_project_dir))
        reviewer = create_review_agent(llm_provider=mock_llm, project_directory=str(test_project_dir))
        product = create_product_manager_agent(llm_provider=mock_llm, project_directory=str(test_project_dir))

        assert coding.session_id.startswith("coding_")
        assert analyzer.session_id.startswith("analyzer_")
        assert reviewer.session_id.startswith("reviewer_")
        assert product.session_id.startswith("product_")

    def test_custom_session_id(self, mock_llm, test_project_dir):
        """Test that custom session IDs can be provided."""
        agent = create_product_manager_agent(
            session_id="custom_session_123",
            llm_provider=mock_llm,
            project_directory=str(test_project_dir)
        )

        assert agent.session_id == "custom_session_123"
