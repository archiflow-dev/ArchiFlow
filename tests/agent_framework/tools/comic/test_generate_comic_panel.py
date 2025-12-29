"""
Tests for GenerateComicPanelTool.

Comprehensive test coverage for comic panel image generation.
"""

import unittest
import asyncio
import os
import json
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import shutil

from agent_framework.tools.comic.generate_comic_panel_tool import GenerateComicPanelTool
from agent_framework.llm.image_provider_base import ImageProvider
from PIL import Image


class MockImageProvider(ImageProvider):
    """Mock image provider for testing."""

    def __init__(self, should_fail=False):
        """Initialize mock provider."""
        self.should_fail = should_fail
        self.generated_prompts = []

    @property
    def provider_name(self) -> str:
        """Return mock provider name."""
        return "mock"

    @property
    def model_name(self) -> str:
        """Return mock model name."""
        return "mock-model"

    def validate_connection(self) -> bool:
        """Validate mock connection."""
        return not self.should_fail

    def generate_image(self, prompt, aspect_ratio="1:1", resolution="1K", ref_images=None, **kwargs):
        """Mock image generation."""
        self.generated_prompts.append(prompt)

        if self.should_fail:
            return None

        # Create a simple test image
        img = Image.new('RGB', (100, 100), color='red')
        return img


class TestGenerateComicPanelTool(unittest.TestCase):
    """Test suite for GenerateComicPanelTool."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_provider = MockImageProvider()
        self.tool = GenerateComicPanelTool(image_provider=self.mock_provider)
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test files."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def parse_output(self, result):
        """Parse JSON output from ToolResult."""
        if result.error:
            return None
        return json.loads(result.output)

    # ===== Initialization Tests =====

    def test_initialization(self):
        """Test tool initialization."""
        self.assertIsNotNone(self.tool)
        self.assertEqual(self.tool.name, "generate_comic_panel")
        self.assertIsNotNone(self.tool.image_provider)
        self.assertIsNotNone(self.tool.character_references)
        self.assertEqual(len(self.tool.character_references), 0)

    def test_initialization_without_provider(self):
        """Test initialization without explicit provider."""
        # Should try to create GoogleImageProvider if GOOGLE_API_KEY exists
        with patch.dict(os.environ, {}, clear=True):
            tool = GenerateComicPanelTool()
            # Provider will be None if no API key
            self.assertIsNone(tool.image_provider)

    def test_tool_schema(self):
        """Test tool schema is correct."""
        schema = self.tool.parameters
        self.assertEqual(schema["type"], "object")
        self.assertIn("prompt", schema["properties"])
        self.assertIn("panel_type", schema["properties"])
        self.assertIn("required", schema)
        self.assertIn("prompt", schema["required"])
        self.assertIn("panel_type", schema["required"])

    def test_tool_description(self):
        """Test tool has proper description."""
        self.assertIn("comic", self.tool.description.lower())
        self.assertIn("panel", self.tool.description.lower())

    # ===== Character Reference Generation Tests =====

    def test_generate_character_reference(self):
        """Test character reference generation."""
        async def run_test():
            result = await self.tool.execute(
                prompt="A brave robot named Artie",
                panel_type="character_reference",
                character_names=["Artie"],
                session_id="test",
                output_dir=self.temp_dir
            )
            self.assertIsNone(result.error)
            output = self.parse_output(result)
            self.assertIsNotNone(output)
            self.assertTrue(output["success"])
            self.assertIn("ARTIE.png", output["filename"])
            self.assertEqual(output["panel_type"], "character_reference")
            self.assertTrue(os.path.exists(output["file_path"]))

        asyncio.run(run_test())

    def test_character_reference_stored(self):
        """Test character reference is stored after generation."""
        async def run_test():
            result = await self.tool.execute(
                prompt="A brave robot named Artie",
                panel_type="character_reference",
                character_names=["Artie"],
                session_id="test",
                output_dir=self.temp_dir
            )
            self.assertIsNone(result.error)

            # Check if character reference was stored
            self.assertIn("Artie", self.tool.character_references)
            ref_image = self.tool.get_character_reference("Artie")
            self.assertIsNotNone(ref_image)
            self.assertIsInstance(ref_image, Image.Image)

        asyncio.run(run_test())

    def test_character_reference_without_name(self):
        """Test character reference generation without character name."""
        async def run_test():
            result = await self.tool.execute(
                prompt="A mysterious character",
                panel_type="character_reference",
                session_id="test",
                output_dir=self.temp_dir
            )
            self.assertIsNone(result.error)
            output = self.parse_output(result)
            self.assertIsNotNone(output)
            self.assertTrue(output["success"])
            # Should default to "character"
            self.assertIn("CHARACTER.png", output["filename"])

        asyncio.run(run_test())

    # ===== Story Panel Generation Tests =====

    def test_generate_story_panel(self):
        """Test story panel generation."""
        async def run_test():
            result = await self.tool.execute(
                prompt="Artie discovers a paintbrush",
                panel_type="establishing_shot",
                page_number=1,
                panel_number=1,
                character_names=["Artie"],
                action="Artie picks up a paintbrush from a table",
                session_id="test",
                output_dir=self.temp_dir
            )
            self.assertIsNone(result.error)
            output = self.parse_output(result)
            self.assertIsNotNone(output)
            self.assertTrue(output["success"])
            self.assertIn("page_01_panel_01.png", output["filename"])
            self.assertEqual(output["page_number"], 1)
            self.assertEqual(output["panel_number"], 1)
            self.assertTrue(os.path.exists(output["file_path"]))

        asyncio.run(run_test())

    def test_panel_without_page_number(self):
        """Test panel generation fails without page number."""
        async def run_test():
            result = await self.tool.execute(
                prompt="Artie discovers a paintbrush",
                panel_type="establishing_shot",
                panel_number=1,
                session_id="test",
                output_dir=self.temp_dir
            )
            self.assertIsNotNone(result.error)
            self.assertIn("page_number", result.error.lower())

        asyncio.run(run_test())

    def test_panel_without_panel_number(self):
        """Test panel generation fails without panel number."""
        async def run_test():
            result = await self.tool.execute(
                prompt="Artie discovers a paintbrush",
                panel_type="establishing_shot",
                page_number=1,
                session_id="test",
                output_dir=self.temp_dir
            )
            self.assertIsNotNone(result.error)
            self.assertIn("panel_number", result.error.lower())

        asyncio.run(run_test())

    # ===== Panel Type Tests =====

    def test_all_panel_types(self):
        """Test all panel types can be generated."""
        panel_types = ["establishing_shot", "action", "dialogue", "close_up", "transition"]

        async def run_test():
            for idx, panel_type in enumerate(panel_types, 1):
                result = await self.tool.execute(
                    prompt=f"Test {panel_type} panel",
                    panel_type=panel_type,
                    page_number=1,
                    panel_number=idx,
                    session_id="test",
                    output_dir=self.temp_dir
                )
                self.assertIsNone(result.error)
                output = self.parse_output(result)
                self.assertIsNotNone(output)
                self.assertTrue(output["success"])
                self.assertEqual(output["panel_type"], panel_type)

        asyncio.run(run_test())

    # ===== Prompt Building Tests =====

    def test_build_comic_prompt_basic(self):
        """Test basic prompt building."""
        prompt = self.tool._build_comic_prompt(
            prompt="Test scene",
            panel_type="action"
        )
        self.assertIn("Test scene", prompt)
        self.assertIn("Comic Book Panel", prompt)
        self.assertIn("Action", prompt)
        self.assertIn("Comic book art", prompt)

    def test_build_comic_prompt_with_characters(self):
        """Test prompt building with characters."""
        prompt = self.tool._build_comic_prompt(
            prompt="Test scene",
            panel_type="action",
            character_names=["Hero", "Villain"]
        )
        self.assertIn("Hero", prompt)
        self.assertIn("Villain", prompt)
        self.assertIn("Characters:", prompt)

    def test_build_comic_prompt_with_action(self):
        """Test prompt building with action."""
        prompt = self.tool._build_comic_prompt(
            prompt="Test scene",
            panel_type="action",
            action="Running"
        )
        self.assertIn("Running", prompt)
        self.assertIn("Action:", prompt)

    def test_build_comic_prompt_with_dialogue(self):
        """Test prompt building with dialogue."""
        prompt = self.tool._build_comic_prompt(
            prompt="Test scene",
            panel_type="dialogue",
            dialogue="Hello, world!"
        )
        self.assertIn("Hello, world!", prompt)
        self.assertIn("Dialogue", prompt)

    def test_build_comic_prompt_with_visual_details(self):
        """Test prompt building with visual details."""
        prompt = self.tool._build_comic_prompt(
            prompt="Test scene",
            panel_type="close_up",
            visual_details="Dramatic lighting from above"
        )
        self.assertIn("Dramatic lighting from above", prompt)
        self.assertIn("Visual Details:", prompt)

    def test_build_comic_prompt_with_page_panel(self):
        """Test prompt building with page and panel numbers."""
        prompt = self.tool._build_comic_prompt(
            prompt="Test scene",
            panel_type="action",
            page_number=2,
            panel_number=3
        )
        self.assertIn("Page 2", prompt)
        self.assertIn("Panel 3", prompt)

    def test_build_comic_prompt_character_reference(self):
        """Test prompt building for character reference."""
        prompt = self.tool._build_comic_prompt(
            prompt="A robot character",
            panel_type="character_reference",
            character_names=["Artie"]
        )
        self.assertIn("Character Reference Sheet", prompt)
        self.assertIn("Full-body character design", prompt)
        self.assertIn("Artie", prompt)

    def test_build_comic_prompt_panel_guidance(self):
        """Test panel type-specific guidance is added."""
        prompt_establishing = self.tool._build_comic_prompt(
            prompt="Test",
            panel_type="establishing_shot"
        )
        self.assertIn("Wide shot", prompt_establishing)

        prompt_action = self.tool._build_comic_prompt(
            prompt="Test",
            panel_type="action"
        )
        self.assertIn("Dynamic composition", prompt_action)

    # ===== File Naming Tests =====

    def test_character_reference_filename(self):
        """Test character reference filename format."""
        async def run_test():
            result = await self.tool.execute(
                prompt="Test character",
                panel_type="character_reference",
                character_names=["TestChar"],
                session_id="test",
                output_dir=self.temp_dir
            )
            self.assertIsNone(result.error)
            output = self.parse_output(result)
            self.assertIsNotNone(output)
            self.assertEqual(output["filename"], "TESTCHAR.png")

        asyncio.run(run_test())

    def test_panel_filename_format(self):
        """Test panel filename format with padding."""
        async def run_test():
            result = await self.tool.execute(
                prompt="Test panel",
                panel_type="action",
                page_number=5,
                panel_number=12,
                session_id="test",
                output_dir=self.temp_dir
            )
            self.assertIsNone(result.error)
            output = self.parse_output(result)
            self.assertIsNotNone(output)
            self.assertEqual(output["filename"], "page_05_panel_12.png")

        asyncio.run(run_test())

    # ===== Directory Creation Tests =====

    def test_auto_create_character_refs_dir(self):
        """Test automatic creation of character_refs directory."""
        async def run_test():
            result = await self.tool.execute(
                prompt="Test character",
                panel_type="character_reference",
                character_names=["TestChar"],
                session_id="test_session",
                output_dir=None  # Let it auto-determine
            )
            # Note: output_dir is auto-determined, so we just check success
            self.assertIsNone(result.error)
            output = self.parse_output(result)
            self.assertIsNotNone(output)
            self.assertTrue(output["success"])

        asyncio.run(run_test())

    def test_auto_create_panels_dir(self):
        """Test automatic creation of panels directory."""
        async def run_test():
            result = await self.tool.execute(
                prompt="Test panel",
                panel_type="action",
                page_number=1,
                panel_number=1,
                session_id="test_session",
                output_dir=None  # Let it auto-determine
            )
            self.assertIsNone(result.error)
            output = self.parse_output(result)
            self.assertIsNotNone(output)
            self.assertTrue(output["success"])

        asyncio.run(run_test())

    # ===== Image Format Tests =====

    def test_image_saved_as_png(self):
        """Test image is saved as PNG format."""
        async def run_test():
            result = await self.tool.execute(
                prompt="Test",
                panel_type="character_reference",
                character_names=["Test"],
                session_id="test",
                output_dir=self.temp_dir
            )
            self.assertIsNone(result.error)
            output = self.parse_output(result)
            self.assertIsNotNone(output)
            self.assertTrue(output["file_path"].endswith(".png"))

            # Verify it's a valid PNG
            img = Image.open(output["file_path"])
            self.assertEqual(img.format, "PNG")

        asyncio.run(run_test())

    # ===== Character Reference Usage Tests =====

    def test_use_character_reference(self):
        """Test using stored character reference."""
        async def run_test():
            # First generate a character reference
            result1 = await self.tool.execute(
                prompt="A brave robot named Artie",
                panel_type="character_reference",
                character_names=["Artie"],
                session_id="test",
                output_dir=self.temp_dir
            )
            self.assertIsNone(result1.error)

            # Now use it in a panel
            result2 = await self.tool.execute(
                prompt="Artie in action",
                panel_type="action",
                page_number=1,
                panel_number=1,
                character_names=["Artie"],
                character_reference="Artie",
                session_id="test",
                output_dir=self.temp_dir
            )
            self.assertIsNone(result2.error)
            output = self.parse_output(result2)
            self.assertIsNotNone(output)
            self.assertTrue(output["success"])

        asyncio.run(run_test())

    def test_clear_references(self):
        """Test clearing character references."""
        async def run_test():
            # Generate a character reference
            result = await self.tool.execute(
                prompt="A brave robot named Artie",
                panel_type="character_reference",
                character_names=["Artie"],
                session_id="test",
                output_dir=self.temp_dir
            )
            self.assertIsNone(result.error)
            self.assertIn("Artie", self.tool.character_references)

            # Clear references
            self.tool.clear_references()
            self.assertEqual(len(self.tool.character_references), 0)
            self.assertIsNone(self.tool.get_character_reference("Artie"))

        asyncio.run(run_test())

    # ===== Error Handling Tests =====

    def test_no_image_provider(self):
        """Test error when no image provider is available."""
        async def run_test():
            # Patch environment to prevent auto-creation of provider
            with patch.dict(os.environ, {}, clear=True):
                tool = GenerateComicPanelTool(image_provider=None)
                # Explicitly set to None to override auto-creation
                tool.image_provider = None
                result = await tool.execute(
                    prompt="Test",
                    panel_type="character_reference",
                    character_names=["Test"],
                    session_id="test"
                )
                self.assertIsNotNone(result.error)
                self.assertIn("image provider", result.error.lower())

        asyncio.run(run_test())

    def test_image_generation_failure(self):
        """Test handling of image generation failure."""
        async def run_test():
            fail_provider = MockImageProvider(should_fail=True)
            tool = GenerateComicPanelTool(image_provider=fail_provider)
            result = await tool.execute(
                prompt="Test",
                panel_type="character_reference",
                character_names=["Test"],
                session_id="test"
            )
            self.assertIsNotNone(result.error)
            self.assertIn("Failed to generate image", result.error)

        asyncio.run(run_test())

    # ===== Aspect Ratio & Resolution Tests =====

    def test_custom_aspect_ratio(self):
        """Test custom aspect ratio."""
        async def run_test():
            result = await self.tool.execute(
                prompt="Test",
                panel_type="character_reference",
                character_names=["Test"],
                aspect_ratio="16:9",
                session_id="test",
                output_dir=self.temp_dir
            )
            self.assertIsNone(result.error)
            output = self.parse_output(result)
            self.assertIsNotNone(output)
            self.assertTrue(output["success"])

        asyncio.run(run_test())

    def test_custom_resolution(self):
        """Test custom resolution."""
        async def run_test():
            result = await self.tool.execute(
                prompt="Test",
                panel_type="character_reference",
                character_names=["Test"],
                resolution="4K",
                session_id="test",
                output_dir=self.temp_dir
            )
            self.assertIsNone(result.error)
            output = self.parse_output(result)
            self.assertIsNotNone(output)
            self.assertTrue(output["success"])

        asyncio.run(run_test())

    # ===== Output Validation Tests =====

    def test_output_contains_required_fields(self):
        """Test output contains all required fields."""
        async def run_test():
            result = await self.tool.execute(
                prompt="Test",
                panel_type="character_reference",
                character_names=["Test"],
                session_id="test",
                output_dir=self.temp_dir
            )
            self.assertIsNone(result.error)
            output = self.parse_output(result)
            self.assertIsNotNone(output)
            self.assertIn("success", output)
            self.assertIn("file_path", output)
            self.assertIn("filename", output)
            self.assertIn("panel_type", output)
            self.assertIn("session_id", output)
            self.assertIn("output_dir", output)
            self.assertIn("image_size", output)
            self.assertIn("message", output)

        asyncio.run(run_test())

    # ===== Repr Test =====

    def test_repr(self):
        """Test string representation."""
        repr_str = repr(self.tool)
        self.assertIn("GenerateComicPanelTool", repr_str)
        self.assertIn("MockImageProvider", repr_str)


if __name__ == '__main__':
    unittest.main()
