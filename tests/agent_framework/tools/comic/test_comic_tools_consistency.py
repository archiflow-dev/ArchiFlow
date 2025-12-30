import pytest
import os
import json
from unittest.mock import MagicMock, patch, ANY
from PIL import Image

from agent_framework.tools.comic.generate_comic_panel_tool import GenerateComicPanelTool
from agent_framework.tools.comic.generate_comic_page_tool import GenerateComicPageTool
from agent_framework.runtime.context import ExecutionContext
from agent_framework.llm.image_provider_base import ImageProvider


class MockImageProvider(ImageProvider):
    """Mock image provider for testing."""

    def __init__(self):
        # Don't call super().__init__ to avoid API key requirement
        self._model_name = "mock-model"
        self.api_key = "mock-key"
        self.generate_image_calls = []

    def generate_image(self, prompt, ref_images=None, **kwargs):
        """Return a dummy image and track the call."""
        self.generate_image_calls.append({'prompt': prompt, 'ref_images': ref_images, 'kwargs': kwargs})
        return Image.new('RGB', (100, 100), color='white')

    @property
    def provider_name(self):
        return "mock"

    @property
    def model_name(self):
        return self._model_name

    def validate_connection(self):
        """Mock connection validation."""
        return True


@pytest.fixture
def mock_image_provider():
    """Create a mock image provider that returns a dummy image."""
    return MockImageProvider()

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
async def test_panel_tool_loads_reference_from_disk(panel_tool):
    """Test that panel tool looks for reference on disk if not in memory."""
    with patch("os.path.exists") as mock_exists, \
         patch("PIL.Image.open") as mock_open:

        # Setup mock behavior
        mock_exists.return_value = True
        mock_ref_img = Image.new('RGB', (10, 10), 'blue')
        mock_open.return_value = mock_ref_img

        # Execute tool
        await panel_tool.execute(
            prompt="test prompt",
            panel_type="action",
            session_id="test_session",
            character_reference="Hero",
            page_number=1,
            panel_number=1
        )

        # Verify it looked for file
        # Check that os.path.join was implicitly checked via exists
        # We expect it to look for HERO.png, Hero.png, etc.
        assert mock_exists.called

        # Verify it loaded the image
        assert mock_open.called

        # Verify it passed the loaded image to provider
        assert len(panel_tool.image_provider.generate_image_calls) >= 1
        call = panel_tool.image_provider.generate_image_calls[-1]
        ref_images = call['ref_images']
        assert len(ref_images) == 1
        assert ref_images[0] == mock_ref_img

        # Verify it cached it
        assert "Hero" in panel_tool.character_references

@pytest.mark.asyncio
async def test_page_tool_direct_mode_collects_references(page_tool):
    """Test that page tool collects references in direct mode."""

    panels = [
        {"panel_number": 1, "prompt": "p1", "panel_type": "scene", "characters": ["Hero"]},
        {"panel_number": 2, "prompt": "p2", "panel_type": "scene", "characters": ["Villain"]}
    ]

    with patch("os.path.exists") as mock_exists, \
         patch("PIL.Image.open") as mock_open:

        # Setup mocks
        mock_exists.return_value = True
        mock_open.return_value = Image.new('RGB', (10, 10), 'red')

        # Execute
        result = await page_tool.execute(
            session_id="test_session",
            page_number=1,
            panels=panels,
            layout="1x2",
            generation_mode="direct"
        )

        # Verify result success
        assert result.output
        data = json.loads(result.output)
        assert data["success"] is True

        # Verify image provider called with references
        assert len(page_tool.image_provider.generate_image_calls) >= 1
        call = page_tool.image_provider.generate_image_calls[0]
        ref_images = call['ref_images']
        # Should have 2 references (Hero and Villain)
        assert len(ref_images) == 2

@pytest.mark.asyncio
async def test_page_tool_stitched_mode_integration(page_tool):
    """Test that stitched mode uses panel tool which uses references."""
    
    panels = [
        {"panel_number": 1, "prompt": "p1", "panel_type": "scene", "characters": ["Hero"]}
    ]
    
    # We need to mock the GenerateComicPanelTool inside the method or rely on the class structure
    # Since generate_comic_page_tool imports it inside the method, patching is tricky.
    # But since we updated GenerateComicPanelTool logic, we can trust unit tests for it.
    # Here we just verify that page tool runs without error in stitched mode.
    
    with patch("agent_framework.tools.comic.generate_comic_panel_tool.GenerateComicPanelTool.execute") as mock_execute:
        # Mock successful panel generation result
        mock_result = MagicMock()
        mock_result.error = None
        mock_result.output = json.dumps({
            "success": True, 
            "file_path": "/tmp/dummy.png",
            "image_size": [100, 100]
        })
        mock_execute.return_value = mock_result
        
        with patch("PIL.Image.open") as mock_open:
            mock_open.return_value = Image.new('RGB', (100, 100))
            
            result = await page_tool.execute(
                session_id="test_session",
                page_number=1,
                panels=panels,
                layout="1x1",
                generation_mode="stitched"
            )
            
            assert json.loads(result.output)["success"] is True
            assert mock_execute.called
