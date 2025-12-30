"""
Test suite for visual style enhancement parameters in comic generation tools.

Tests that the tools correctly accept and process visual parameters
(art_style, color_palette, lighting, special_effects, composition, etc.)
as specified in the gap analysis document.
"""

import pytest
import os
import json
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
# PAGE TOOL TESTS - Visual Parameter Acceptance
# ============================================================================

class TestPageToolVisualParameters:
    """Test that page tool accepts and processes visual parameters correctly."""

    @pytest.mark.asyncio
    async def test_page_tool_accepts_art_style(self, page_tool):
        """Test that page tool accepts art_style parameter."""
        panels = [
            {"panel_number": 1, "prompt": "p1", "panel_type": "scene"}
        ]
        result = await page_tool.execute(
            session_id="test_session",
            page_number=1,
            panels=panels,
            layout="1x1",
            generation_mode="direct",
            art_style="Cinematic sci-fi with Blade Runner influences"
        )
        assert result.error is None

    @pytest.mark.asyncio
    async def test_page_tool_accepts_global_color_palette(self, page_tool):
        """Test that page tool accepts global_color_palette parameter."""
        panels = [
            {"panel_number": 1, "prompt": "p1", "panel_type": "scene"}
        ]
        color_palette = {
            "Cold Technology": ["Cyan (#00D9FF)", "Electric Blue (#2B6CB0)"],
            "Human Warmth": ["Amber (#F6AD55)", "Orange (#DD6B20)"],
            "Nature/Life": ["Forest Green (#38A169)", "Bioluminescent Purple (#9F7AEA)"]
        }
        result = await page_tool.execute(
            session_id="test_session",
            page_number=1,
            panels=panels,
            layout="1x1",
            generation_mode="direct",
            global_color_palette=color_palette
        )
        assert result.error is None

    @pytest.mark.asyncio
    async def test_page_tool_accepts_global_lighting(self, page_tool):
        """Test that page tool accepts global_lighting parameter."""
        panels = [
            {"panel_number": 1, "prompt": "p1", "panel_type": "scene"}
        ]
        result = await page_tool.execute(
            session_id="test_session",
            page_number=1,
            panels=panels,
            layout="1x1",
            generation_mode="direct",
            global_lighting="Cathedral/god rays for ARIA's awakening, natural golden hour for human scenes"
        )
        assert result.error is None

    @pytest.mark.asyncio
    async def test_page_tool_accepts_character_specs(self, page_tool):
        """Test that page tool accepts character_specs parameter."""
        panels = [
            {"panel_number": 1, "prompt": "p1", "panel_type": "scene", "characters": ["ARIA"]}
        ]
        character_specs = [
            {
                "name": "ARIA",
                "appearance": "Humanoid holographic projection of shifting geometric light patterns",
                "colors": ["Electric Blue (#00D9FF)", "Deep Purple (#6B46C1)", "White glow (#FFFFFF)"],
                "special_effects": "Constant subtle motion - patterns flowing like liquid light"
            }
        ]
        result = await page_tool.execute(
            session_id="test_session",
            page_number=1,
            panels=panels,
            layout="1x1",
            generation_mode="direct",
            character_specs=character_specs
        )
        assert result.error is None

    @pytest.mark.asyncio
    async def test_page_tool_accepts_per_panel_visuals(self, page_tool):
        """Test that page tool accepts per_panel_visuals parameter."""
        panels = [
            {"panel_number": 1, "prompt": "p1", "panel_type": "scene"},
            {"panel_number": 2, "prompt": "p2", "panel_type": "scene"}
        ]
        per_panel_visuals = [
            {
                "panel_number": 1,
                "color_palette": ["Electric Blue (#00D9FF)", "Deep Cyan (#008080)"],
                "lighting": "God rays streaming from ceiling",
                "special_effects": "Digital glitch effects",
                "composition": "Symmetrical vanishing point"
            },
            {
                "panel_number": 2,
                "color_palette": ["White (#FFFFFF)", "Blue glow"],
                "lighting": "Screen glow illuminating darkness"
            }
        ]
        result = await page_tool.execute(
            session_id="test_session",
            page_number=1,
            panels=panels,
            layout="1x2",
            generation_mode="direct",
            per_panel_visuals=per_panel_visuals
        )
        assert result.error is None

    @pytest.mark.asyncio
    async def test_page_tool_all_visual_parameters(self, page_tool):
        """Test that page tool accepts all visual parameters together."""
        panels = [
            {"panel_number": 1, "prompt": "p1", "panel_type": "scene", "characters": ["ARIA"]}
        ]
        color_palette = {
            "dominant": ["Electric Blue (#00D9FF)"]
        }
        character_specs = [
            {"name": "ARIA", "appearance": "Holographic projection"}
        ]
        per_panel_visuals = [
            {
                "panel_number": 1,
                "color_palette": ["Electric Blue (#00D9FF)"],
                "lighting": "God rays"
            }
        ]

        result = await page_tool.execute(
            session_id="test_session",
            page_number=1,
            panels=panels,
            layout="1x1",
            generation_mode="direct",
            art_style="Cinematic sci-fi",
            global_color_palette=color_palette,
            global_lighting="Cathedral lighting",
            character_specs=character_specs,
            per_panel_visuals=per_panel_visuals
        )
        assert result.error is None


# ============================================================================
# PAGE TOOL TESTS - Prompt Building with Visuals
# ============================================================================

class TestPageToolPromptBuilding:
    """Test that visual information is correctly formatted in page prompts."""

    @pytest.mark.asyncio
    async def test_page_prompt_includes_art_style(self, page_tool):
        """Test that art_style is included in generated page prompt."""
        panels = [
            {"panel_number": 1, "prompt": "p1", "panel_type": "scene"}
        ]
        await page_tool.execute(
            session_id="test_session",
            page_number=1,
            panels=panels,
            layout="1x1",
            generation_mode="direct",
            art_style="Cinematic science fiction with Blade Runner influences"
        )

        assert len(page_tool.image_provider.generate_image_calls) >= 1
        call = page_tool.image_provider.generate_image_calls[0]
        prompt = call['kwargs'].get('prompt') or call['prompt']

        assert "=== OVERALL ART STYLE ===" in prompt
        assert "Cinematic science fiction with Blade Runner influences" in prompt

    @pytest.mark.asyncio
    async def test_page_prompt_includes_global_color_palette(self, page_tool):
        """Test that global_color_palette is included in generated page prompt."""
        panels = [
            {"panel_number": 1, "prompt": "p1", "panel_type": "scene"}
        ]
        color_palette = {
            "Cold Technology": ["Cyan (#00D9FF)", "Electric Blue (#2B6CB0)"],
            "Human Warmth": ["Amber (#F6AD55)"]
        }
        await page_tool.execute(
            session_id="test_session",
            page_number=1,
            panels=panels,
            layout="1x1",
            generation_mode="direct",
            global_color_palette=color_palette
        )

        call = page_tool.image_provider.generate_image_calls[0]
        prompt = call['kwargs'].get('prompt') or call['prompt']

        assert "=== GLOBAL COLOR PALETTE ===" in prompt
        assert "Cold Technology" in prompt
        assert "Cyan (#00D9FF)" in prompt
        assert "Human Warmth" in prompt
        assert "Amber (#F6AD55)" in prompt

    @pytest.mark.asyncio
    async def test_page_prompt_includes_global_lighting(self, page_tool):
        """Test that global_lighting is included in generated page prompt."""
        panels = [
            {"panel_number": 1, "prompt": "p1", "panel_type": "scene"}
        ]
        await page_tool.execute(
            session_id="test_session",
            page_number=1,
            panels=panels,
            layout="1x1",
            generation_mode="direct",
            global_lighting="Cathedral/god rays for ARIA's awakening, natural golden hour for human scenes"
        )

        call = page_tool.image_provider.generate_image_calls[0]
        prompt = call['kwargs'].get('prompt') or call['prompt']

        assert "=== GLOBAL LIGHTING PHILOSOPHY ===" in prompt
        assert "Cathedral/god rays" in prompt
        assert "natural golden hour" in prompt

    @pytest.mark.asyncio
    async def test_page_prompt_includes_character_specs(self, page_tool):
        """Test that character_specs is included in generated page prompt."""
        panels = [
            {"panel_number": 1, "prompt": "p1", "panel_type": "scene", "characters": ["ARIA"]}
        ]
        character_specs = [
            {
                "name": "ARIA",
                "appearance": "Humanoid holographic projection composed of shifting geometric light patterns",
                "colors": ["Electric Blue (#00D9FF)", "Deep Purple (#6B46C1)"],
                "special_effects": "Constant subtle motion - patterns flowing like liquid light"
            }
        ]
        await page_tool.execute(
            session_id="test_session",
            page_number=1,
            panels=panels,
            layout="1x1",
            generation_mode="direct",
            character_specs=character_specs
        )

        call = page_tool.image_provider.generate_image_calls[0]
        prompt = call['kwargs'].get('prompt') or call['prompt']

        assert "=== CHARACTER SPECIFICATIONS ===" in prompt
        assert "ARIA" in prompt
        assert "Humanoid holographic projection" in prompt
        assert "Electric Blue (#00D9FF)" in prompt
        assert "Constant subtle motion" in prompt

    @pytest.mark.asyncio
    async def test_page_prompt_includes_per_panel_visuals(self, page_tool):
        """Test that per_panel_visuals is included in generated page prompt."""
        panels = [
            {"panel_number": 1, "prompt": "p1", "panel_type": "scene"},
            {"panel_number": 2, "prompt": "p2", "panel_type": "scene"}
        ]
        per_panel_visuals = [
            {
                "panel_number": 1,
                "color_palette": ["Electric Blue (#00D9FF)", "Deep Cyan (#008080)"],
                "lighting": ["God rays streaming from ceiling", "Blue glow from servers"],
                "special_effects": ["Digital glitch effects"],
                "composition": ["Symmetrical vanishing point"]
            },
            {
                "panel_number": 2,
                "color_palette": ["White (#FFFFFF)"],
                "lighting": ["Screen glow illuminating darkness"]
            }
        ]
        await page_tool.execute(
            session_id="test_session",
            page_number=1,
            panels=panels,
            layout="1x2",
            generation_mode="direct",
            per_panel_visuals=per_panel_visuals
        )

        call = page_tool.image_provider.generate_image_calls[0]
        prompt = call['kwargs'].get('prompt') or call['prompt']

        # Should include per-panel visual details integrated into panel descriptions
        # Panel 1 visuals
        assert "Panel 1" in prompt
        assert "God rays streaming from ceiling" in prompt
        assert "Blue glow from servers" in prompt
        assert "Digital glitch effects" in prompt
        assert "Symmetrical vanishing point" in prompt

        # Panel 2 visuals
        assert "Panel 2" in prompt
        assert "Screen glow illuminating darkness" in prompt


# ============================================================================
# BACKWARD COMPATIBILITY TESTS
# ============================================================================

class TestBackwardCompatibility:
    """Test that tools work without visual parameters (backward compatibility)."""

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
    async def test_page_tool_works_without_visual_parameters(self, page_tool):
        """Test that page tool works without any visual parameters."""
        panels = [
            {"panel_number": 1, "prompt": "p1", "panel_type": "scene"}
        ]
        result = await page_tool.execute(
            session_id="test_session",
            page_number=1,
            panels=panels,
            layout="1x1",
            generation_mode="direct"
        )
        assert result.error is None
        # Should still generate image
        assert len(page_tool.image_provider.generate_image_calls) >= 1


# ============================================================================
# PANEL NOTE TESTS - Special Layout Instructions
# ============================================================================

class TestPanelNoteSpecialLayouts:
    """Test that panel_note special layout instructions are included in prompts."""

    @pytest.mark.asyncio
    async def test_full_page_splash_panel_note(self, page_tool):
        """Test that full-page splash panel note is included in prompt."""
        panels = [
            {
                "panel_number": 1,
                "prompt": "Cosmic cathedral consciousness visualization",
                "panel_type": "action",
                "panel_note": "FULL-PAGE SPLASH: This panel occupies entire page (2048x2730) with NO gutters or borders, bleeds to all edges"
            }
        ]
        await page_tool.execute(
            session_id="test_session",
            page_number=3,
            panels=panels,
            layout="1x1",
            generation_mode="direct"
        )

        assert len(page_tool.image_provider.generate_image_calls) >= 1
        call = page_tool.image_provider.generate_image_calls[0]
        prompt = call['kwargs'].get('prompt') or call['prompt']

        # Should include the special layout instruction prominently
        # Check for key text (markdown asterisks may be processed)
        assert "SPECIAL LAYOUT:" in prompt
        assert "FULL-PAGE SPLASH" in prompt
        assert "NO gutters or borders" in prompt
        assert "bleeds to all edges" in prompt

    @pytest.mark.asyncio
    async def test_wide_panel_note(self, page_tool):
        """Test that wide panel note is included in prompt."""
        panels = [
            {
                "panel_number": 1,
                "prompt": "Protest montage",
                "panel_type": "scene",
                "panel_note": "WIDE PANEL: This panel spans the full width of the page"
            }
        ]
        await page_tool.execute(
            session_id="test_session",
            page_number=2,
            panels=panels,
            layout="2x3",
            generation_mode="direct"
        )

        call = page_tool.image_provider.generate_image_calls[0]
        prompt = call['kwargs'].get('prompt') or call['prompt']

        assert "SPECIAL LAYOUT:" in prompt
        assert "WIDE PANEL" in prompt
        assert "spans the full width" in prompt

    @pytest.mark.asyncio
    async def test_half_page_splash_panel_note(self, page_tool):
        """Test that half-page splash panel note is included in prompt."""
        panels = [
            {"panel_number": 1, "prompt": "Military forces", "panel_type": "action"},
            {
                "panel_number": 2,
                "prompt": "ARIA's planetary consciousness",
                "panel_type": "scene",
                "panel_note": "HALF-PAGE SPLASH: This panel spans full width and occupies 50% of page height"
            }
        ]
        await page_tool.execute(
            session_id="test_session",
            page_number=5,
            panels=panels,
            layout="2x3",
            generation_mode="direct"
        )

        call = page_tool.image_provider.generate_image_calls[0]
        prompt = call['kwargs'].get('prompt') or call['prompt']

        assert "SPECIAL LAYOUT:" in prompt
        assert "HALF-PAGE SPLASH" in prompt
        assert "spans full width" in prompt
        assert "50% of page height" in prompt

    @pytest.mark.asyncio
    async def test_panel_note_without_special_layout(self, page_tool):
        """Test that panels without panel_note work normally."""
        panels = [
            {"panel_number": 1, "prompt": "Standard panel", "panel_type": "scene"}
        ]
        await page_tool.execute(
            session_id="test_session",
            page_number=1,
            panels=panels,
            layout="2x3",
            generation_mode="direct"
        )

        call = page_tool.image_provider.generate_image_calls[0]
        prompt = call['kwargs'].get('prompt') or call['prompt']

        # Should NOT have special layout instruction
        assert "SPECIAL LAYOUT:" not in prompt
