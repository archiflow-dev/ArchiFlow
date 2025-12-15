"""
Unit tests for TechLeadAgent.

These tests verify the core functionality of the tech lead agent,
including mode detection, documentation generation, and workflow handling.
"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

from agent_framework.agents.tech_lead_agent import TechLeadAgent
from agent_framework.llm.mock import MockLLMProvider
from agent_framework.llm.provider import LLMResponse
from agent_framework.messages.types import (
    UserMessage, ToolResultObservation, AgentFinishedMessage,
    ToolCallMessage, LLMRespondMessage
)


@pytest.fixture
def mock_llm():
    """Create a mock LLM provider."""
    return MockLLMProvider()


@pytest.fixture
def empty_project_dir(tmp_path):
    """Create an empty project directory."""
    return tmp_path


@pytest.fixture
def project_with_complete_docs(tmp_path):
    """Create a project with complete documentation."""
    # Create docs directory
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()

    # Create complete documentation
    (docs_dir / "PRODUCT_REQUIREMENTS.md").write_text("# Product Requirements")
    (docs_dir / "TECHNICAL_SPEC.md").write_text("# Technical Specification")
    (docs_dir / "USER_STORIES.md").write_text("# User Stories")

    return tmp_path


@pytest.fixture
def project_with_partial_docs(tmp_path):
    """Create a project with partial documentation."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()

    # Only one document
    (docs_dir / "notes.md").write_text("# Some notes about the project")

    return tmp_path


@pytest.fixture
def project_with_code(tmp_path):
    """Create a project with existing code."""
    src_dir = tmp_path / "src"
    src_dir.mkdir()

    # Add some Python files
    (src_dir / "main.py").write_text("print('Hello')")
    (src_dir / "app.py").write_text("def main(): pass")

    return tmp_path


@pytest.fixture
def test_agent_empty(mock_llm, empty_project_dir):
    """Create a test agent with empty project."""
    return TechLeadAgent(
        session_id="test_session",
        llm=mock_llm,
        project_directory=str(empty_project_dir)
    )


@pytest.fixture
def test_agent_complete_docs(mock_llm, project_with_complete_docs):
    """Create a test agent with complete documentation."""
    return TechLeadAgent(
        session_id="test_session",
        llm=mock_llm,
        project_directory=str(project_with_complete_docs)
    )


@pytest.fixture
def test_agent_partial_docs(mock_llm, project_with_partial_docs):
    """Create a test agent with partial documentation."""
    return TechLeadAgent(
        session_id="test_session",
        llm=mock_llm,
        project_directory=str(project_with_partial_docs)
    )


@pytest.fixture
def test_agent_with_code(mock_llm, project_with_code):
    """Create a test agent with existing code."""
    return TechLeadAgent(
        session_id="test_session",
        llm=mock_llm,
        project_directory=str(project_with_code)
    )


class TestAgentInitialization:
    """Test agent initialization and setup."""

    def test_agent_creation(self, test_agent_empty, empty_project_dir):
        """Test that agent can be created successfully."""
        assert test_agent_empty.session_id == "test_session"
        assert test_agent_empty.project_directory == empty_project_dir
        assert test_agent_empty.is_running is True
        assert test_agent_empty.agent_name == "TechLeadAgent"
        assert test_agent_empty.agent_version == "1.0.0"

    def test_project_directory_validation(self, mock_llm):
        """Test that invalid project directory raises error."""
        with pytest.raises(ValueError, match="does not exist"):
            TechLeadAgent(
                session_id="test",
                llm=mock_llm,
                project_directory="/nonexistent/path"
            )

    def test_default_project_directory(self, mock_llm):
        """Test that agent uses cwd if no directory specified."""
        agent = TechLeadAgent(
            session_id="test",
            llm=mock_llm
        )
        assert agent.project_directory == Path.cwd()

    def test_allowed_tools_list(self, test_agent_empty):
        """Test that allowed_tools list is correct."""
        expected = ["todo_write", "todo_read", "write", "read", "list", "glob", "grep", "finish_task"]
        assert test_agent_empty.allowed_tools == expected

    def test_tool_filtering(self, test_agent_empty):
        """Test that only appropriate tools are exposed to LLM."""
        schema = test_agent_empty._get_tools_schema()
        schema_tool_names = [tool['function']['name'] for tool in schema]

        # Verify allowed tools are in schema
        for tool in test_agent_empty.allowed_tools:
            assert tool in schema_tool_names

        # Verify dangerous tools are NOT in schema
        assert "edit" not in schema_tool_names
        assert "bash" not in schema_tool_names
        assert "multi_edit" not in schema_tool_names


class TestModeDetection:
    """Test the agent's mode detection logic."""

    def test_detect_complete_docs(self, test_agent_complete_docs):
        """Test detection of complete documentation."""
        assert test_agent_complete_docs._has_complete_docs() is True
        assert test_agent_complete_docs._has_partial_docs() is True
        assert test_agent_complete_docs._has_existing_code() is False

    def test_detect_partial_docs(self, test_agent_partial_docs):
        """Test detection of partial documentation."""
        assert test_agent_partial_docs._has_complete_docs() is False
        assert test_agent_partial_docs._has_partial_docs() is True
        assert test_agent_partial_docs._has_existing_code() is False

    def test_detect_no_docs(self, test_agent_empty):
        """Test detection of no documentation."""
        assert test_agent_empty._has_complete_docs() is False
        assert test_agent_empty._has_partial_docs() is False
        assert test_agent_empty._has_existing_code() is False

    def test_detect_existing_code(self, test_agent_with_code):
        """Test detection of existing code."""
        assert test_agent_with_code._has_complete_docs() is False
        assert test_agent_with_code._has_partial_docs() is False
        assert test_agent_with_code._has_existing_code() is True

    def test_detect_readme_as_partial(self, mock_llm, tmp_path):
        """Test that README.md counts as partial documentation."""
        (tmp_path / "README.md").write_text("# Project")
        agent = TechLeadAgent("test", mock_llm, str(tmp_path))
        assert agent._has_partial_docs() is True


class TestSystemPromptGeneration:
    """Test dynamic system prompt generation based on mode."""

    def test_prompt_for_discovery_mode(self, test_agent_empty):
        """Test system prompt includes DISCOVERY MODE for empty project."""
        prompt = test_agent_empty.get_system_message()
        assert "DISCOVERY MODE" in prompt
        assert "ANALYSIS MODE" not in prompt
        assert "HYBRID MODE" not in prompt
        assert "INTEGRATION MODE" not in prompt
        assert "MODE DETECTION" in prompt

    def test_prompt_for_analysis_mode(self, test_agent_complete_docs):
        """Test system prompt includes ANALYSIS MODE for complete docs."""
        prompt = test_agent_complete_docs.get_system_message()
        assert "ANALYSIS MODE" in prompt
        assert "DISCOVERY MODE" not in prompt
        assert "HYBRID MODE" not in prompt
        assert "INTEGRATION MODE" not in prompt

    def test_prompt_for_hybrid_mode(self, test_agent_partial_docs):
        """Test system prompt includes HYBRID MODE for partial docs."""
        prompt = test_agent_partial_docs.get_system_message()
        assert "HYBRID MODE" in prompt
        assert "DISCOVERY MODE" not in prompt
        assert "ANALYSIS MODE" not in prompt
        assert "INTEGRATION MODE" not in prompt

    def test_prompt_for_integration_mode(self, test_agent_with_code):
        """Test system prompt includes INTEGRATION MODE for existing code."""
        prompt = test_agent_with_code.get_system_message()
        assert "INTEGRATION MODE" in prompt
        assert "DISCOVERY MODE" not in prompt
        assert "ANALYSIS MODE" not in prompt
        assert "HYBRID MODE" not in prompt

    def test_prompt_includes_universal_guidelines(self, test_agent_empty):
        """Test that all prompts include universal guidelines."""
        prompt = test_agent_empty.get_system_message()
        assert "UNIVERSAL GUIDELINES" in prompt
        assert "COMPLETION CRITERIA" in prompt
        assert "Tech Lead Agent" in prompt
        assert "project directory is:" in prompt

    def test_prompt_includes_diagram_instructions(self, test_agent_empty):
        """Test that prompts include diagram generation instructions."""
        prompt = test_agent_empty.get_system_message()
        assert "ASCII/Unicode Diagrams" in prompt
        assert "Mermaid Diagrams" in prompt


class TestMessageProcessing:
    """Test the step() method message processing."""

    def test_step_with_user_message_discovery_mode(self, test_agent_empty):
        """Test processing user message in discovery mode."""
        # Mock tool calls for documentation discovery
        mock_tool_call = Mock()
        mock_tool_call.id = "call_1"
        mock_tool_call.name = "glob"
        mock_tool_call.arguments = '{"pattern": "docs/*.md"}'

        mock_response = Mock(spec=LLMResponse)
        mock_response.content = "I'm entering DISCOVERY MODE - let's gather requirements..."
        mock_response.tool_calls = [mock_tool_call]
        test_agent_empty.llm.generate = Mock(return_value=mock_response)

        user_msg = UserMessage(
            session_id="test_session",
            sequence=0,
            content="I want to build a social media app"
        )

        response = test_agent_empty.step(user_msg)

        assert isinstance(response, ToolCallMessage)
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].tool_name == "glob"
        assert "DISCOVERY MODE" in mock_response.content

    def test_step_with_user_message_analysis_mode(self, test_agent_complete_docs):
        """Test processing user message in analysis mode."""
        # Mock reading existing documentation
        mock_tool_call = Mock()
        mock_tool_call.id = "call_1"
        mock_tool_call.name = "read"
        mock_tool_call.arguments = '{"file_path": "docs/PRODUCT_REQUIREMENTS.md"}'

        mock_response = Mock(spec=LLMResponse)
        mock_response.content = "I'm entering ANALYSIS MODE - I found your requirements..."
        mock_response.tool_calls = [mock_tool_call]
        test_agent_complete_docs.llm.generate = Mock(return_value=mock_response)

        user_msg = UserMessage(
            session_id="test_session",
            sequence=0,
            content="I have product requirements ready"
        )

        response = test_agent_complete_docs.step(user_msg)

        assert isinstance(response, ToolCallMessage)
        assert response.tool_calls[0].tool_name == "read"
        assert "ANALYSIS MODE" in mock_response.content

    def test_step_creates_requirements_doc(self, test_agent_empty):
        """Test that agent creates requirements document in discovery mode."""
        # Mock checking for docs then creating requirements
        mock_calls = [
            Mock(id="call_1", name="glob", arguments='{"pattern": "docs/*.md"}'),
            Mock(id="call_2", name="write", arguments='{"file_path": "docs/BUSINESS_REQUIREMENTS.md", "content": "# Business Requirements"}')
        ]

        mock_response = Mock(spec=LLMResponse)
        mock_response.content = "Let me gather your requirements..."
        mock_response.tool_calls = mock_calls
        test_agent_empty.llm.generate = Mock(return_value=mock_response)

        user_msg = UserMessage(
            session_id="test_session",
            sequence=0,
            content="I need to build an e-commerce platform"
        )

        response = test_agent_empty.step(user_msg)

        assert isinstance(response, ToolCallMessage)
        assert len(response.tool_calls) == 2
        assert response.tool_calls[0].tool_name == "glob"
        assert response.tool_calls[1].tool_name == "write"
        assert "BUSINESS_REQUIREMENTS.md" in response.tool_calls[1].arguments

    def test_step_creates_architecture_doc(self, test_agent_complete_docs):
        """Test that agent creates architecture documentation."""
        # Mock reading requirements then creating architecture
        mock_calls = [
            Mock(id="call_1", name="read", arguments='{"file_path": "docs/PRODUCT_REQUIREMENTS.md"}'),
            Mock(id="call_2", name="write", arguments='{"file_path": "docs/architecture/README.md", "content": "# System Architecture"}')
        ]

        mock_response = Mock(spec=LLMResponse)
        mock_response.content = "I'll design the architecture..."
        mock_response.tool_calls = mock_calls
        test_agent_complete_docs.llm.generate = Mock(return_value=mock_response)

        user_msg = UserMessage(
            session_id="test_session",
            sequence=0,
            content="Design the architecture for this"
        )

        response = test_agent_complete_docs.step(user_msg)

        assert isinstance(response, ToolCallMessage)
        assert response.tool_calls[1].tool_name == "write"
        assert "architecture/README.md" in response.tool_calls[1].arguments


class TestFinishTask:
    """Test the finish_task handling."""

    def test_finish_task_with_architecture_summary(self, test_agent_complete_docs):
        """Test that finish_task creates AgentFinishedMessage with architecture summary."""
        architecture_summary = """Architecture Documentation Created:
- docs/architecture/README.md (System overview)
- docs/architecture/decisions/001-microservices.md (ADR)
- docs/architecture/diagrams/system-context.md (Diagrams)

Implementation Plan:
- Phase 1: Foundation services
- Phase 2: API Gateway
- Phase 3: UI Integration

Next Steps:
- Ready for coding agent to implement
- Command: /new coding
"""

        mock_tool_call = Mock()
        mock_tool_call.id = "call_finish"
        mock_tool_call.name = "finish_task"
        mock_tool_call.arguments = json.dumps({
            "reason": "Architecture design complete",
            "result": architecture_summary
        })

        mock_response = Mock(spec=LLMResponse)
        mock_response.content = "Architecture documentation complete."
        mock_response.tool_calls = [mock_tool_call]
        test_agent_complete_docs.llm.generate = Mock(return_value=mock_response)

        user_msg = UserMessage(
            session_id="test_session",
            sequence=0,
            content="Generate the implementation plan"
        )

        response = test_agent_complete_docs.step(user_msg)

        assert isinstance(response, AgentFinishedMessage)
        assert architecture_summary in response.reason
        assert "Architecture design complete" in response.reason
        assert test_agent_complete_docs.is_running is False


class TestDocumentationCreation:
    """Test documentation creation capabilities."""

    def test_creates_rfc_document(self, test_agent_empty):
        """Test that agent can create RFC documents."""
        mock_tool_call = Mock()
        mock_tool_call.id = "call_1"
        mock_tool_call.name = "write"
        mock_tool_call.arguments = json.dumps({
            "file_path": "docs/architecture/rfcs/001-microservices-decision.md",
            "content": """# RFC-001: Microservices Architecture Decision

## Status: Proposed

## Context
We need to scale the application...

## Proposed Solution
Adopt microservices architecture...

## Alternatives
1. Monolith
2. Modular monolith

## Decision
Microservices because...
"""
        })

        mock_response = Mock(spec=LLMResponse)
        mock_response.content = "Creating RFC for architecture decision..."
        mock_response.tool_calls = [mock_tool_call]
        test_agent_empty.llm.generate = Mock(return_value=mock_response)

        user_msg = UserMessage(
            session_id="test_session",
            sequence=0,
            content="Should we use microservices?"
        )

        response = test_agent_empty.step(user_msg)

        assert isinstance(response, ToolCallMessage)
        assert "rfcs/001-microservices-decision.md" in response.tool_calls[0].arguments

    def test_creates_implementation_plan(self, test_agent_empty):
        """Test that agent creates detailed implementation plan."""
        mock_tool_call = Mock()
        mock_tool_call.id = "call_1"
        mock_tool_call.name = "write"
        mock_tool_call.arguments = json.dumps({
            "file_path": "docs/architecture/implementation/plan.md",
            "content": """# Implementation Plan

## Phase 0: Foundation (Week 1-2)
- [ ] Setup project structure
- [ ] CI/CD pipeline
- [ ] Database schema

## Phase 1: Core Services (Week 3-6)
- [ ] User service
- [ ] Auth service
- [ ] API gateway
"""
        })

        mock_response = Mock(spec=LLMResponse)
        mock_response.content = "Creating implementation plan..."
        mock_response.tool_calls = [mock_tool_call]
        test_agent_empty.llm.generate = Mock(return_value=mock_response)

        user_msg = UserMessage(
            session_id="test_session",
            sequence=0,
            content="Break this down into implementation tasks"
        )

        response = test_agent_empty.step(user_msg)

        assert isinstance(response, ToolCallMessage)
        assert "implementation/plan.md" in response.tool_calls[0].arguments
        assert "Phase 0: Foundation" in response.tool_calls[0].arguments

    def test_creates_ascii_diagram(self, test_agent_empty):
        """Test that agent creates ASCII diagrams in documentation."""
        diagram = """```
┌─────────────┐     ┌─────────────┐
│   Client    │────▶│  API GW     │
└─────────────┘     └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   Service   │
                    └─────────────┘
```"""

        mock_tool_call = Mock()
        mock_tool_call.id = "call_1"
        mock_tool_call.name = "write"
        mock_tool_call.arguments = json.dumps({
            "file_path": "docs/architecture/diagrams/overview.md",
            "content": f"# System Overview\n\n{diagram}"
        })

        mock_response = Mock(spec=LLMResponse)
        mock_response.content = "Creating architecture diagram..."
        mock_response.tool_calls = [mock_tool_call]
        test_agent_empty.llm.generate = Mock(return_value=mock_response)

        user_msg = UserMessage(
            session_id="test_session",
            sequence=0,
            content="Show me the architecture"
        )

        response = test_agent_empty.step(user_msg)

        assert isinstance(response, ToolCallMessage)
        assert diagram in response.tool_calls[0].arguments


class TestErrorHandling:
    """Test error handling scenarios."""

    def test_missing_tools_raises_error(self, mock_llm, tmp_path):
        """Test that missing required tools raises an error."""
        # Create agent with empty tool registry
        from agent_framework.tools.tool_base import ToolRegistry
        empty_registry = ToolRegistry()

        with pytest.raises(ValueError, match="Missing required tools"):
            TechLeadAgent(
                session_id="test",
                llm=mock_llm,
                project_directory=str(tmp_path),
                tools=empty_registry
            )

    def test_step_when_not_running(self, test_agent_empty):
        """Test that step returns None when agent is not running."""
        test_agent_empty.is_running = False

        user_msg = UserMessage(
            session_id="test_session",
            sequence=0,
            content="Test"
        )

        response = test_agent_empty.step(user_msg)
        assert response is None

    def test_debug_logging(self, mock_llm, tmp_path, tmp_path_factory):
        """Test debug logging functionality."""
        log_dir = tmp_path_factory.mktemp("logs")
        log_path = log_dir / "debug.log"

        agent = TechLeadAgent(
            session_id="test",
            llm=mock_llm,
            project_directory=str(tmp_path),
            debug_log_path=str(log_path)
        )

        assert agent.debug_log_path == str(log_path)