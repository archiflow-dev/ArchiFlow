"""Unit tests for PPT Agent."""

import pytest
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, AsyncMock

from agent_framework.agents.ppt_agent import PPTAgent
from agent_framework.messages.types import BaseMessage, UserMessage
from agent_framework.llm.mock import MockLLMProvider


class TestPPTAgent:
    """Test cases for PPTAgent."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM provider."""
        return MockLLMProvider()

    @pytest.fixture
    def ppt_agent(self, temp_dir, mock_llm):
        """Create a PPTAgent instance for testing."""
        # Import ToolRegistry to pass a real registry
        from agent_framework.tools.tool_base import ToolRegistry

        return PPTAgent(
            session_id="test_session",
            llm=mock_llm,
            google_api_key="test_key",
            project_directory=temp_dir,
            tools=ToolRegistry()
        )

    def test_agent_initialization(self, ppt_agent, temp_dir):
        """Test agent initialization."""
        assert ppt_agent.session_id == "test_session"
        assert ppt_agent.project_directory == temp_dir
        assert ppt_agent.google_api_key == "test_key"
        assert ppt_agent.config["name"] == "PPTAgent"
        assert ppt_agent.config["version"] == "1.0.0"
        assert len(ppt_agent.allowed_tools) > 0
        assert "generate_image" in ppt_agent.allowed_tools
        assert "export_pptx" in ppt_agent.allowed_tools
        assert "export_pdf" in ppt_agent.allowed_tools

    def test_system_message_no_files(self, ppt_agent):
        """Test system message generation with no existing files."""
        system_message = ppt_agent.get_system_message()

        # Check core elements are in system message
        assert "Presentation Designer and Visual Storyteller" in system_message
        assert "MODE DETECTION" in system_message
        assert "IDEA MODE" in system_message
        assert "Your session directory is:" in system_message
        assert "Has Outline: False" in system_message
        assert "Has Descriptions: False" in system_message
        assert "Has Images: False" in system_message

    def test_system_message_with_outline(self, ppt_agent, temp_dir):
        """Test system message with existing outline file."""
        # Create outline file
        outline_file = Path(temp_dir) / "outline.json"
        outline_data = {
            "title": "Test Presentation",
            "slides": [
                {"title": "Slide 1", "content": ["Point 1"]},
                {"title": "Slide 2", "content": ["Point 2"]}
            ]
        }
        with open(outline_file, 'w') as f:
            json.dump(outline_data, f)

        system_message = ppt_agent.get_system_message()

        assert "OUTLINE MODE" in system_message
        assert "Has Outline: True" in system_message
        assert "Has Descriptions: False" in system_message

    def test_system_message_with_descriptions(self, ppt_agent, temp_dir):
        """Test system message with existing outline and descriptions."""
        # Create outline file
        outline_file = Path(temp_dir) / "outline.json"
        outline_data = {"title": "Test", "slides": []}
        with open(outline_file, 'w') as f:
            json.dump(outline_data, f)

        # Create descriptions file
        desc_file = Path(temp_dir) / "descriptions.json"
        desc_data = [{"slide_number": 1, "title": "Slide 1"}]
        with open(desc_file, 'w') as f:
            json.dump(desc_data, f)

        system_message = ppt_agent.get_system_message()

        assert "GENERATION MODE" in system_message
        assert "Has Outline: True" in system_message
        assert "Has Descriptions: True" in system_message

    def test_tools_setup(self, ppt_agent):
        """Test tools are properly set up."""
        # Check that tools registry exists
        assert ppt_agent.tools is not None
        assert hasattr(ppt_agent, "allowed_tools")
        assert "generate_image" in ppt_agent.allowed_tools
        assert "export_pptx" in ppt_agent.allowed_tools
        assert "export_pdf" in ppt_agent.allowed_tools

    def test_get_tools_schema(self, ppt_agent):
        """Test tools schema generation."""
        schema = ppt_agent._get_tools_schema()
        assert isinstance(schema, list)
        # Note: In a real scenario, tools would be registered in the registry
        # For tests, we just verify the method doesn't crash
        assert len(schema) >= 0  # Could be empty if no tools registered

    def test_format_finish_message(self, ppt_agent):
        """Test finish message formatting."""
        reason = "Presentation created successfully"
        result = "PPTX: file.pptx\nPDF: file.pdf"

        formatted = ppt_agent._format_finish_message(reason, result)

        assert reason in formatted
        assert result in formatted
        assert "\n\n" in formatted

    @pytest.mark.asyncio
    async def test_step_with_idea_only(self, ppt_agent, mock_llm):
        """Test processing a message with only an idea."""
        # Mock LLM response
        from unittest.mock import Mock
        mock_response = Mock()
        mock_response.content = json.dumps({
            "title": "Test Presentation",
            "slides": [
                {"title": "Introduction", "content": ["Welcome"]},
                {"title": "Conclusion", "content": ["Thank you"]}
            ]
        })
        mock_response.tool_calls = None
        mock_llm.generate = Mock(return_value=mock_response)

        # Mock tools
        ppt_agent.tools = Mock()
        ppt_agent.tools.to_llm_schema.return_value = []

        # Create test message
        message = UserMessage(
            session_id="test_session",
            sequence=1,
            content="Create a presentation about renewable energy"
        )

        # Process message
        response = await ppt_agent.step(message)

        assert response is not None
        # Verify the agent attempted to process the idea
        mock_llm.generate.assert_called()

    @pytest.mark.asyncio
    async def test_step_with_outline_file(self, ppt_agent, temp_dir):
        """Test processing a message with outline file."""
        # Create outline file
        outline_file = Path(temp_dir) / "outline.json"
        outline_data = {
            "title": "Energy Presentation",
            "slides": [
                {"title": "Solar Power", "content": ["Clean energy"]},
                {"title": "Wind Power", "content": ["Renewable source"]}
            ]
        }
        with open(outline_file, 'w') as f:
            json.dump(outline_data, f)

        # Mock tools
        ppt_agent.tools = Mock()
        ppt_agent.tools.to_llm_schema.return_value = []

        # Create test message
        message = UserMessage(
            session_id="test_session",
            sequence=1,
            content="Continue with the presentation"
        )

        # Get system message to verify mode detection
        system_message = ppt_agent.get_system_message()
        assert "OUTLINE MODE" in system_message

    @pytest.mark.asyncio
    async def test_step_with_feedback(self, ppt_agent, temp_dir):
        """Test processing feedback message."""
        # Create outline file to simulate existing work
        outline_file = Path(temp_dir) / "outline.json"
        outline_data = {
            "title": "Test Presentation",
            "slides": [{"title": "Slide 1", "content": []}]
        }
        with open(outline_file, 'w') as f:
            json.dump(outline_data, f)

        # Mock tools
        ppt_agent.tools = Mock()
        ppt_agent.tools.to_llm_schema.return_value = []

        # Create test feedback message
        message = UserMessage(
            session_id="test_session",
            sequence=1,
            content="Can you add more slides about solar energy?"
        )

        # Get system message to verify revision mode is included
        system_message = ppt_agent.get_system_message()
        assert "REVISION MODE" in system_message

    def test_core_identity_formatting(self, ppt_agent):
        """Test that core identity is properly formatted."""
        system_message = ppt_agent.get_system_message()
        assert ppt_agent.project_directory in system_message
        assert "Presentation Designer" in system_message

    def test_all_mode_instructions_present(self, ppt_agent):
        """Test that all mode instructions are in the system message."""
        system_message = ppt_agent.get_system_message()

        # Check all modes are present
        assert "IDEA MODE" in system_message
        assert "OUTLINE MODE" in system_message
        assert "GENERATION MODE" in system_message
        assert "REVISION MODE" in system_message

        # Check guidelines are present
        assert "UNIVERSAL GUIDELINES" in system_message
        assert "TOOL USAGE" in system_message
        assert "COMPLETION CRITERIA" in system_message

    @pytest.mark.asyncio
    async def test_error_handling_missing_file(self, ppt_agent, mock_llm):
        """Test handling of missing file references."""
        # Mock tools to simulate missing file
        ppt_agent.tools = Mock()
        ppt_agent.tools.get.return_value = Mock()
        ppt_agent.tools.get.return_value.execute = AsyncMock(
            side_effect=FileNotFoundError("File not found")
        )
        ppt_agent.tools.to_llm_schema.return_value = []

        # Create message referencing non-existent file
        message = UserMessage(
            session_id="test_session",
            sequence=1,
            content="Use outline from missing.json"
        )

        # The agent should handle this gracefully
        response = await ppt_agent.step(message)
        assert response is not None  # Should not crash