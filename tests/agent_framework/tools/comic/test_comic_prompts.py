import pytest
import os
from unittest.mock import MagicMock, patch, ANY
from PIL import Image

from agent_framework.tools.comic.generate_comic_panel_tool import GenerateComicPanelTool
from agent_framework.tools.comic.generate_comic_page_tool import GenerateComicPageTool
from agent_framework.runtime.context import ExecutionContext

@pytest.fixture
def mock_image_provider():
    provider = MagicMock()
    # Return a dummy image
    img = Image.new('RGB', (100, 100), color='white')
    provider.generate_image.return_value = img
    return provider

@pytest.fixture
def panel_tool(mock_image_provider):
    tool = GenerateComicPanelTool(image_provider=mock_image_provider)
    tool.execution_context = ExecutionContext(session_id="test_session", working_directory="/tmp/test")
    return tool

@pytest.fixture
def page_tool(mock_image_provider):
    tool = GenerateComicPageTool(image_provider=mock_image_provider)
    tool.execution_context = ExecutionContext(session_id="test_session", working_directory="/tmp/test")
    return tool

@pytest.mark.asyncio
async def test_panel_tool_adds_instructions(panel_tool):
    """Test that panel tool adds instructions when references are used."""
    with patch("os.path.exists") as mock_exists, \
         patch("PIL.Image.open") as mock_open:
        
        mock_exists.return_value = True
        mock_open.return_value = Image.new('RGB', (10, 10))
        
        await panel_tool.execute(
            prompt="test prompt",
            panel_type="action",
            session_id="test_session",
            character_reference="Hero",
            page_number=1,
            panel_number=1
        )
        
        # Verify prompt contains instruction
        call_args = panel_tool.image_provider.generate_image.call_args
        kwargs = call_args.kwargs
        prompt = kwargs["prompt"]
        
        assert "CRITICAL INSTRUCTION: references provided" in prompt
        assert "maintain strict visual consistency" in prompt

@pytest.mark.asyncio
async def test_panel_tool_no_instructions_without_ref(panel_tool):
    """Test that panel tool does NOT add instructions when no references used."""
    await panel_tool.execute(
        prompt="test prompt",
        panel_type="action",
        session_id="test_session",
        page_number=1,
        panel_number=1
    )
    
    # Verify prompt does NOT contain instruction
    call_args = panel_tool.image_provider.generate_image.call_args
    kwargs = call_args.kwargs
    prompt = kwargs["prompt"]
    
    assert "CRITICAL INSTRUCTION" not in prompt

@pytest.mark.asyncio
async def test_page_tool_adds_instructions(page_tool):
    """Test that page tool adds instructions when references are collected."""
    panels = [{"panel_number": 1, "prompt": "p1", "panel_type": "scene", "characters": ["Hero"]}]
    
    with patch("os.path.exists") as mock_exists, \
         patch("PIL.Image.open") as mock_open:
        
        mock_exists.return_value = True
        mock_open.return_value = Image.new('RGB', (10, 10))
        
        await page_tool.execute(
            session_id="test_session",
            page_number=1,
            panels=panels,
            layout="1x1",
            generation_mode="direct"
        )
        
        # Verify prompt contains instruction
        call_args = page_tool.image_provider.generate_image.call_args
        kwargs = call_args.kwargs
        prompt = kwargs["prompt"]
        
        assert "CRITICAL INSTRUCTION: references provided" in prompt
        assert "maintain strict visual consistency" in prompt
