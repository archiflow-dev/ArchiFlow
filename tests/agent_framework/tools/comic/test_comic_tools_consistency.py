"""
Test suite for comic tools consistency - ensuring character references work correctly.
"""

import pytest
import os
import json
import tempfile
import shutil
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
async def test_page_tool_collects_character_references(page_tool):
    """Test that page tool collects character references correctly."""
    # Use manual temp dir for Windows file locking issues
    tmpdir = tempfile.mkdtemp()
    try:
        # Create required directory structure
        session_dir = os.path.join(tmpdir, "data", "sessions", "test_session")
        pages_dir = os.path.join(session_dir, "pages")
        logs_dir = os.path.join(pages_dir, "logs")
        refs_dir = os.path.join(session_dir, "character_refs")
        os.makedirs(logs_dir, exist_ok=True)
        os.makedirs(refs_dir, exist_ok=True)

        # Create reference images
        hero_img = Image.new('RGB', (100, 100), 'blue')
        villain_img = Image.new('RGB', (100, 100), 'red')
        hero_img.save(os.path.join(refs_dir, "Hero.png"))
        villain_img.save(os.path.join(refs_dir, "Villain.png"))
        hero_img.close()
        villain_img.close()

        # Override the base_dir calculation
        original_join = os.path.join
        def patched_join(*args):
            if args and args[0] == "data" and len(args) > 1 and args[1] == "sessions":
                return original_join(tmpdir, *args)
            return original_join(*args)

        with patch('agent_framework.tools.comic.generate_comic_page_tool.os.path.join', side_effect=patched_join):
            page_prompt = "Test page prompt with Hero and Villain characters"
            characters = ["Hero", "Villain"]

            result = await page_tool.execute(
                session_id="test_session",
                page_number=1,
                page_prompt=page_prompt,
                characters=characters
            )

            # Verify image provider was called
            assert len(page_tool.image_provider.generate_image_calls) >= 1
            call = page_tool.image_provider.generate_image_calls[0]
            ref_images = call['ref_images']

            # Should have found references (2 characters)
            assert len(ref_images) == 2

            # Close loaded images to release file handles
            for img in ref_images:
                if hasattr(img, 'close'):
                    img.close()
    finally:
        # Clean up with error handling for Windows
        shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.mark.asyncio
async def test_page_tool_accepts_simplified_api(page_tool):
    """Test that page tool accepts the simplified API with page_prompt."""
    # Use manual temp dir for Windows file locking issues
    tmpdir = tempfile.mkdtemp()
    try:
        # Create required directory structure
        session_dir = os.path.join(tmpdir, "data", "sessions", "test_session")
        pages_dir = os.path.join(session_dir, "pages")
        logs_dir = os.path.join(pages_dir, "logs")
        os.makedirs(logs_dir, exist_ok=True)

        # Override the base_dir calculation
        original_join = os.path.join
        def patched_join(*args):
            if args and args[0] == "data" and len(args) > 1 and args[1] == "sessions":
                return original_join(tmpdir, *args)
            return original_join(*args)

        with patch('agent_framework.tools.comic.generate_comic_page_tool.os.path.join', side_effect=patched_join):
            page_prompt = """
            === PAGE 1: TEST PAGE ===

            LAYOUT:
            - Template: 3x3 Standard Grid
            - Panel Count: 9

            PANELS:
            Panel 1: Test scene
            """

            result = await page_tool.execute(
                session_id="test_session",
                page_number=1,
                page_prompt=page_prompt
            )

            # Should have called the image provider
            assert len(page_tool.image_provider.generate_image_calls) >= 1

            # The prompt should be passed through
            call = page_tool.image_provider.generate_image_calls[0]
            actual_prompt = call['prompt']
            assert "PAGE 1" in actual_prompt
            assert "Panel 1" in actual_prompt
    finally:
        # Clean up with error handling for Windows
        shutil.rmtree(tmpdir, ignore_errors=True)
