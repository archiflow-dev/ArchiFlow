"""
Test suite for comic tool prompt generation with character references.
"""

import pytest
import os
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
async def test_panel_tool_adds_instructions(mock_image_provider):
    """Test that panel tool adds instructions when references are used."""
    # Use manual temp dir for Windows file locking issues
    tmpdir = tempfile.mkdtemp()
    try:
        # Create directory structure - tool uses working_directory/character_refs/
        refs_dir = os.path.join(tmpdir, "character_refs")
        panels_dir = os.path.join(tmpdir, "panels")
        os.makedirs(refs_dir, exist_ok=True)
        os.makedirs(panels_dir, exist_ok=True)

        # Create a reference image
        ref_img = Image.new('RGB', (100, 100), 'blue')
        ref_path = os.path.join(refs_dir, "Hero.png")
        ref_img.save(ref_path)
        ref_img.close()

        # Create tool with working_directory pointing to our temp dir
        tool = GenerateComicPanelTool(image_provider=mock_image_provider)
        tool.execution_context = ExecutionContext(
            session_id="test_session",
            working_directory=tmpdir
        )

        await tool.execute(
            prompt="test prompt",
            panel_type="action",
            session_id="test_session",
            character_reference="Hero",
            page_number=1,
            panel_number=1
        )

        # Verify prompt contains instruction
        assert len(tool.image_provider.generate_image_calls) >= 1
        call = tool.image_provider.generate_image_calls[-1]
        prompt = call['kwargs'].get('prompt') or call['prompt']

        assert "CRITICAL INSTRUCTION: references provided" in prompt
        assert "maintain strict visual consistency" in prompt

        # Close any loaded images
        for char_name, img in tool.character_references.items():
            if hasattr(img, 'close'):
                img.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


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
    assert len(panel_tool.image_provider.generate_image_calls) >= 1
    call = panel_tool.image_provider.generate_image_calls[-1]
    prompt = call['kwargs'].get('prompt') or call['prompt']

    assert "CRITICAL INSTRUCTION" not in prompt


@pytest.mark.asyncio
async def test_page_tool_adds_instructions(mock_image_provider):
    """Test that page tool adds instructions when references are collected."""
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

        # Create a reference image
        ref_img = Image.new('RGB', (100, 100), 'blue')
        ref_path = os.path.join(refs_dir, "Hero.png")
        ref_img.save(ref_path)
        ref_img.close()

        # Create tool
        tool = GenerateComicPageTool(image_provider=mock_image_provider)
        tool.execution_context = ExecutionContext(
            session_id="test_session",
            working_directory="/tmp/test"
        )

        # Override the base_dir calculation by patching os.path.join
        original_join = os.path.join
        def patched_join(*args):
            if args and args[0] == "data" and len(args) > 1 and args[1] == "sessions":
                return original_join(tmpdir, *args)
            return original_join(*args)

        with patch('agent_framework.tools.comic.generate_comic_page_tool.os.path.join', side_effect=patched_join):
            page_prompt = "Test prompt for page generation with characters"
            characters = ["Hero"]

            await tool.execute(
                session_id="test_session",
                page_number=1,
                page_prompt=page_prompt,
                characters=characters
            )

            # Verify prompt contains instruction (added when refs are loaded)
            assert len(tool.image_provider.generate_image_calls) >= 1
            call = tool.image_provider.generate_image_calls[-1]
            prompt = call['prompt']

            # When character references are found, the tool appends consistency instructions
            assert "CRITICAL INSTRUCTION" in prompt
            assert "maintain strict visual consistency" in prompt

            # Close any loaded images to release file handles
            for img in call.get('ref_images', []) or []:
                if hasattr(img, 'close'):
                    img.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
