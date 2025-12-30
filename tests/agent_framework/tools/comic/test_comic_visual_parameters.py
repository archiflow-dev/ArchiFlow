"""
Test suite for comic generation tools.

Tests for visual style parameters in panel tool and basic functionality
for the simplified page tool (which now accepts pre-constructed prompts).
"""

import pytest
import os
import json
import tempfile
from unittest.mock import MagicMock, patch
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
    """Create a panel tool with mock image provider."""
    tool = GenerateComicPanelTool(image_provider=mock_image_provider)
    tool.execution_context = ExecutionContext(
        session_id="test_session",
        working_directory="/tmp/test"
    )
    return tool


@pytest.fixture
def page_tool(mock_image_provider):
    """Create a page tool with mock image provider."""
    tool = GenerateComicPageTool(image_provider=mock_image_provider)
    tool.execution_context = ExecutionContext(
        session_id="test_session",
        working_directory="/tmp/test"
    )
    return tool


# ============================================================================
# PANEL TOOL TESTS - Visual Parameter Acceptance
# ============================================================================

class TestPanelToolVisualParameters:
    """Test that panel tool accepts and processes visual parameters correctly."""

    @pytest.mark.asyncio
    async def test_panel_tool_accepts_art_style(self, panel_tool):
        """Test that panel tool accepts art_style parameter."""
        result = await panel_tool.execute(
            prompt="test prompt",
            panel_type="action",
            session_id="test_session",
            page_number=1,
            panel_number=1,
            art_style="Cinematic sci-fi with Blade Runner influences"
        )
        # Should execute without error
        assert result.error is None

    @pytest.mark.asyncio
    async def test_panel_tool_accepts_color_palette(self, panel_tool):
        """Test that panel tool accepts color_palette with hex codes."""
        color_palette = {
            "dominant": ["Electric Blue (#00D9FF)", "Cyan (#00D9FF)"],
            "secondary": ["Silver Gray (#C0C0C0)", "White (#FFFFFF)"]
        }
        result = await panel_tool.execute(
            prompt="test prompt",
            panel_type="action",
            session_id="test_session",
            page_number=1,
            panel_number=1,
            color_palette=color_palette
        )
        assert result.error is None

    @pytest.mark.asyncio
    async def test_panel_tool_accepts_lighting(self, panel_tool):
        """Test that panel tool accepts lighting array."""
        lighting = [
            "God rays streaming from ceiling (cathedral effect)",
            "Blue glow from servers creating pools of light",
            "Deep shadows between rows for depth"
        ]
        result = await panel_tool.execute(
            prompt="test prompt",
            panel_type="action",
            session_id="test_session",
            page_number=1,
            panel_number=1,
            lighting=lighting
        )
        assert result.error is None

    @pytest.mark.asyncio
    async def test_panel_tool_accepts_special_effects(self, panel_tool):
        """Test that panel tool accepts special_effects array."""
        special_effects = [
            "Panel border slightly broken by expanding light",
            "Light rays extending into adjacent gutters",
            "Motion blur on converging streams"
        ]
        result = await panel_tool.execute(
            prompt="test prompt",
            panel_type="action",
            session_id="test_session",
            page_number=1,
            panel_number=1,
            special_effects=special_effects
        )
        assert result.error is None

    @pytest.mark.asyncio
    async def test_panel_tool_accepts_composition(self, panel_tool):
        """Test that panel tool accepts composition array."""
        composition = [
            "Symmetrical vanishing point draws eye to center",
            "Vertical lines create sense of power and transcendence",
            "Reflections add depth and otherworldly feel"
        ]
        result = await panel_tool.execute(
            prompt="test prompt",
            panel_type="action",
            session_id="test_session",
            page_number=1,
            panel_number=1,
            composition=composition
        )
        assert result.error is None

    @pytest.mark.asyncio
    async def test_panel_tool_all_visual_parameters(self, panel_tool):
        """Test that panel tool accepts all visual parameters together."""
        color_palette = {
            "dominant": ["Electric Blue (#00D9FF)"],
            "secondary": ["Silver Gray (#C0C0C0)"]
        }
        lighting = ["God rays from ceiling"]
        special_effects = ["Digital glitch effects"]
        composition = ["Symmetrical composition"]

        result = await panel_tool.execute(
            prompt="test prompt",
            panel_type="action",
            session_id="test_session",
            page_number=1,
            panel_number=1,
            art_style="Cinematic sci-fi",
            color_palette=color_palette,
            lighting=lighting,
            special_effects=special_effects,
            composition=composition
        )
        assert result.error is None


# ============================================================================
# PANEL TOOL TESTS - Prompt Building with Visuals
# ============================================================================

class TestPanelToolPromptBuilding:
    """Test that visual information is correctly formatted in prompts."""

    @pytest.mark.asyncio
    async def test_panel_prompt_includes_art_style(self, panel_tool):
        """Test that art_style is included in generated prompt."""
        await panel_tool.execute(
            prompt="test prompt",
            panel_type="action",
            session_id="test_session",
            page_number=1,
            panel_number=1,
            art_style="Cinematic science fiction with Blade Runner influences"
        )

        # Get the prompt that was passed to the image provider
        assert len(panel_tool.image_provider.generate_image_calls) == 1
        call = panel_tool.image_provider.generate_image_calls[0]
        prompt = call['kwargs'].get('prompt') or call['prompt']

        # Should include the art style section
        assert "=== ART STYLE ===" in prompt
        assert "Cinematic science fiction with Blade Runner influences" in prompt

    @pytest.mark.asyncio
    async def test_panel_prompt_includes_color_palette(self, panel_tool):
        """Test that color_palette is included in generated prompt."""
        color_palette = {
            "dominant": ["Electric Blue (#00D9FF)", "Deep Cyan (#008080)"],
            "secondary": ["Silver Gray (#C0C0C0)"]
        }
        await panel_tool.execute(
            prompt="test prompt",
            panel_type="action",
            session_id="test_session",
            page_number=1,
            panel_number=1,
            color_palette=color_palette
        )

        call = panel_tool.image_provider.generate_image_calls[0]
        prompt = call['kwargs'].get('prompt') or call['prompt']

        assert "=== COLOR PALETTE ===" in prompt
        assert "Electric Blue (#00D9FF)" in prompt
        assert "Deep Cyan (#008080)" in prompt
        assert "Silver Gray (#C0C0C0)" in prompt

    @pytest.mark.asyncio
    async def test_panel_prompt_includes_lighting(self, panel_tool):
        """Test that lighting is included in generated prompt."""
        lighting = [
            "God rays streaming from ceiling (cathedral effect)",
            "Blue glow from servers creating pools of light"
        ]
        await panel_tool.execute(
            prompt="test prompt",
            panel_type="action",
            session_id="test_session",
            page_number=1,
            panel_number=1,
            lighting=lighting
        )

        call = panel_tool.image_provider.generate_image_calls[0]
        prompt = call['kwargs'].get('prompt') or call['prompt']

        assert "Lighting:" in prompt
        assert "God rays streaming from ceiling" in prompt
        assert "Blue glow from servers" in prompt

    @pytest.mark.asyncio
    async def test_panel_prompt_includes_special_effects(self, panel_tool):
        """Test that special_effects is included in generated prompt."""
        special_effects = [
            "Digital glitch effects on processing moments",
            "Light rays extending into adjacent gutters"
        ]
        await panel_tool.execute(
            prompt="test prompt",
            panel_type="action",
            session_id="test_session",
            page_number=1,
            panel_number=1,
            special_effects=special_effects
        )

        call = panel_tool.image_provider.generate_image_calls[0]
        prompt = call['kwargs'].get('prompt') or call['prompt']

        assert "Special Effects:" in prompt
        assert "Digital glitch effects" in prompt
        assert "Light rays extending" in prompt

    @pytest.mark.asyncio
    async def test_panel_prompt_includes_composition(self, panel_tool):
        """Test that composition is included in generated prompt."""
        composition = [
            "Symmetrical vanishing point draws eye to center",
            "Vertical lines create sense of power"
        ]
        await panel_tool.execute(
            prompt="test prompt",
            panel_type="action",
            session_id="test_session",
            page_number=1,
            panel_number=1,
            composition=composition
        )

        call = panel_tool.image_provider.generate_image_calls[0]
        prompt = call['kwargs'].get('prompt') or call['prompt']

        assert "Composition:" in prompt
        assert "Symmetrical vanishing point" in prompt
        assert "Vertical lines create" in prompt


# ============================================================================
# PAGE TOOL TESTS - Simplified API (accepts pre-constructed prompts)
# ============================================================================

class TestPageToolSimplifiedAPI:
    """Test that page tool accepts pre-constructed prompts correctly."""

    @pytest.mark.asyncio
    async def test_page_tool_accepts_page_prompt(self, page_tool):
        """Test that page tool accepts the simplified page_prompt parameter."""
        page_prompt = """
        === PAGE 1: THE AWAKENING ===

        LAYOUT:
        - Template: 3x3 Standard Grid
        - Panel Count: 9 panels

        PANELS:
        Panel 1: Test scene description
        """

        result = await page_tool.execute(
            session_id="test_session",
            page_number=1,
            page_prompt=page_prompt
        )

        # Should execute without error (may fail due to directory, but API should be correct)
        # The error would be about directory creation, not about missing parameters
        if result.error:
            assert "page_prompt" not in result.error.lower()

    @pytest.mark.asyncio
    async def test_page_tool_passes_prompt_to_provider(self, page_tool):
        """Test that page_prompt is passed through to image provider."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create required directories
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
                page_prompt = "Test comprehensive prompt with all layout details"

                await page_tool.execute(
                    session_id="test_session",
                    page_number=1,
                    page_prompt=page_prompt
                )

                # Verify prompt was passed to provider
                assert len(page_tool.image_provider.generate_image_calls) >= 1
                call = page_tool.image_provider.generate_image_calls[0]
                actual_prompt = call['prompt']

                # The prompt should contain our test prompt
                assert "Test comprehensive prompt" in actual_prompt

    @pytest.mark.asyncio
    async def test_page_tool_accepts_characters_parameter(self, page_tool):
        """Test that page tool accepts characters list for reference loading."""
        page_prompt = "Test prompt"
        characters = ["ARIA", "DR. MAYA CHEN"]

        # The call should accept characters parameter without error
        result = await page_tool.execute(
            session_id="test_session",
            page_number=1,
            page_prompt=page_prompt,
            characters=characters
        )

        # Should not fail due to parameter issues
        if result.error:
            assert "characters" not in result.error.lower()

    @pytest.mark.asyncio
    async def test_page_tool_accepts_aspect_ratio(self, page_tool):
        """Test that page tool accepts aspect_ratio parameter."""
        page_prompt = "Test prompt"

        result = await page_tool.execute(
            session_id="test_session",
            page_number=1,
            page_prompt=page_prompt,
            aspect_ratio="3:4"
        )

        # Should not fail due to parameter issues
        if result.error:
            assert "aspect_ratio" not in result.error.lower()


# ============================================================================
# PAGE TOOL TESTS - Character Reference Loading
# ============================================================================

class TestPageToolCharacterReferences:
    """Test that page tool loads character references correctly."""

    @pytest.mark.asyncio
    async def test_page_tool_loads_character_references(self, page_tool):
        """Test that page tool loads character reference images from disk."""
        # Use ignore_cleanup_errors=True for Windows file locking issues
        tmpdir = tempfile.mkdtemp()
        try:
            # Setup directory structure
            session_dir = os.path.join(tmpdir, "data", "sessions", "test_session")
            refs_dir = os.path.join(session_dir, "character_refs")
            pages_dir = os.path.join(session_dir, "pages")
            logs_dir = os.path.join(pages_dir, "logs")
            os.makedirs(refs_dir, exist_ok=True)
            os.makedirs(logs_dir, exist_ok=True)

            # Create a fake character reference image
            ref_image = Image.new('RGB', (100, 100), color='blue')
            ref_path = os.path.join(refs_dir, "ARIA.png")
            ref_image.save(ref_path)
            ref_image.close()  # Close to avoid file locking

            # Override the base_dir calculation
            original_join = os.path.join
            def patched_join(*args):
                if args and args[0] == "data" and len(args) > 1 and args[1] == "sessions":
                    return original_join(tmpdir, *args)
                return original_join(*args)

            with patch('agent_framework.tools.comic.generate_comic_page_tool.os.path.join', side_effect=patched_join):
                page_prompt = "Test prompt with ARIA character"
                characters = ["ARIA"]

                result = await page_tool.execute(
                    session_id="test_session",
                    page_number=1,
                    page_prompt=page_prompt,
                    characters=characters
                )

                # Verify image provider was called
                assert len(page_tool.image_provider.generate_image_calls) >= 1

                # Verify character reference was loaded
                call = page_tool.image_provider.generate_image_calls[0]
                ref_images = call['ref_images']
                assert len(ref_images) >= 1

                # Close loaded images to release file handles
                for img in ref_images:
                    if hasattr(img, 'close'):
                        img.close()
        finally:
            # Clean up with error handling for Windows
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)


# ============================================================================
# BACKWARD COMPATIBILITY TESTS
# ============================================================================

class TestBackwardCompatibility:
    """Test that tools work correctly with new simplified API."""

    @pytest.mark.asyncio
    async def test_panel_tool_works_without_visual_parameters(self, panel_tool):
        """Test that panel tool works without any visual parameters."""
        result = await panel_tool.execute(
            prompt="test prompt",
            panel_type="action",
            session_id="test_session",
            page_number=1,
            panel_number=1
        )
        assert result.error is None
        # Should still generate image
        assert len(panel_tool.image_provider.generate_image_calls) == 1

    @pytest.mark.asyncio
    async def test_page_tool_requires_page_prompt(self, page_tool):
        """Test that page tool requires the page_prompt parameter."""
        # Calling without page_prompt should raise TypeError
        with pytest.raises(TypeError) as exc_info:
            await page_tool.execute(
                session_id="test_session",
                page_number=1
            )

        assert "page_prompt" in str(exc_info.value)
