"""
Unit tests for GenerateImageTool.
"""

import pytest
import os
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock
from PIL import Image

from agent_framework.tools.ppt.generate_image_tool import GenerateImageTool
from agent_framework.llm.google_image_provider import GoogleImageProvider
from agent_framework.llm.image_provider_base import ImageProvider


class MockImageProvider(ImageProvider):
    """Mock image provider for testing."""

    def __init__(self, api_key=None):
        super().__init__(api_key)
        self._provider_name = "mock"
        self._model_name = "mock-model"
        self.reference_image = None
        self.call_count = 0

    @property
    def provider_name(self) -> str:
        return self._provider_name

    @property
    def model_name(self) -> str:
        return self._model_name

    def generate_image(self, prompt, ref_images=None, aspect_ratio="1:1", resolution="1K"):
        """Generate a mock image."""
        self.call_count += 1
        # Create a simple test image
        return Image.new('RGB', (1920, 1080), color=(100, 150, 200))

    def generate_first_slide(self, prompt, aspect_ratio="16:9", resolution="2K"):
        """Generate first slide with reference."""
        image = self.generate_image(prompt, aspect_ratio=aspect_ratio, resolution=resolution)
        self.reference_image = image
        return image

    def generate_subsequent_slide(self, prompt, slide_number, aspect_ratio="16:9", resolution="2K"):
        """Generate subsequent slide using reference."""
        if not self.reference_image:
            return self.generate_first_slide(prompt, aspect_ratio, resolution)
        return self.generate_image(prompt, ref_images=[self.reference_image], aspect_ratio=aspect_ratio, resolution=resolution)

    def validate_connection(self):
        """Mock validation."""
        return True


@pytest.fixture
def mock_image_provider():
    """Create a mock image provider for testing."""
    return MockImageProvider()


@pytest.fixture
def generate_image_tool(mock_image_provider):
    """Create a GenerateImageTool with mock provider."""
    return GenerateImageTool(image_provider=mock_image_provider)


class TestGenerateImageTool:
    """Test cases for GenerateImageTool."""

    def test_tool_initialization_with_provider(self, mock_image_provider):
        """Test tool initialization with a provided image provider."""
        tool = GenerateImageTool(image_provider=mock_image_provider)

        assert tool.name == "generate_image"
        assert tool.image_provider == mock_image_provider
        assert "slide_number" in tool.parameters["required"]
        assert "prompt" in tool.parameters["required"]

    def test_tool_initialization_without_provider(self):
        """Test tool initialization without provider (should create Google provider)."""
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "test_key"}):
            with patch('agent_framework.tools.ppt.generate_image_tool.GoogleImageProvider') as mock_google:
                mock_google.return_value = Mock(spec=GoogleImageProvider)

                tool = GenerateImageTool()

                assert tool.image_provider is not None
                mock_google.assert_called_once_with(api_key="test_key")

    def test_tool_initialization_no_api_key(self):
        """Test tool initialization when no API key is available."""
        with patch.dict(os.environ, {}, clear=True):
            with patch('agent_framework.tools.ppt.generate_image_tool.GoogleImageProvider') as mock_google:
                mock_google.side_effect = Exception("No API key")

                tool = GenerateImageTool()

                assert tool.image_provider is None

    @pytest.mark.asyncio
    async def test_generate_first_slide(self, generate_image_tool, mock_image_provider):
        """Test generating the first slide (establishes reference)."""
        result = await generate_image_tool.execute(
            prompt="Solar panels on a green roof",
            slide_number=1
        )

        assert result.error is None
        assert "slide_001.png" in result.output
        assert mock_image_provider.reference_image is not None
        assert mock_image_provider.call_count == 1

    @pytest.mark.asyncio
    async def test_generate_subsequent_slide(self, generate_image_tool, mock_image_provider):
        """Test generating subsequent slides using reference."""
        # First, generate the reference slide
        await generate_image_tool.execute(
            prompt="First slide",
            slide_number=1
        )

        # Reset call count to track only the second slide
        call_count_before = mock_image_provider.call_count

        # Generate second slide
        result = await generate_image_tool.execute(
            prompt="Wind turbines in a field",
            slide_number=2
        )

        assert result.error is None
        assert "slide_002.png" in result.output
        assert mock_image_provider.call_count > call_count_before

    @pytest.mark.asyncio
    async def test_generate_slide_no_provider(self):
        """Test error handling when no image provider is available."""
        # Use the field directly to set it to None
        tool = GenerateImageTool()
        tool.image_provider = None

        result = await tool.execute(
            prompt="Test slide",
            slide_number=1
        )

        assert result.error is not None
        # The error should mention no image provider
        assert "No image provider available" in result.error

    @pytest.mark.asyncio
    async def test_generate_slide_provider_failure(self, mock_image_provider):
        """Test error handling when provider fails to generate image."""
        mock_image_provider.generate_first_slide = Mock(return_value=None)

        tool = GenerateImageTool(image_provider=mock_image_provider)

        result = await tool.execute(
            prompt="Test slide",
            slide_number=1
        )

        assert result.error is not None
        assert "Failed to generate image" in result.error

    @pytest.mark.asyncio
    async def test_generate_slide_custom_aspect_ratio(self, generate_image_tool, mock_image_provider):
        """Test generating slide with custom aspect ratio."""
        # Reset call count and track the method
        mock_image_provider.call_count = 0

        await generate_image_tool.execute(
            prompt="Square slide",
            slide_number=1,
            aspect_ratio="1:1"
        )

        # Check that the provider was called
        assert mock_image_provider.call_count > 0

    @pytest.mark.asyncio
    async def test_generate_slide_custom_resolution(self, generate_image_tool, mock_image_provider):
        """Test generating slide with custom resolution."""
        # Reset call count and track the method
        mock_image_provider.call_count = 0

        await generate_image_tool.execute(
            prompt="High res slide",
            slide_number=1,
            resolution="4K"
        )

        # Check that the provider was called
        assert mock_image_provider.call_count > 0

    @pytest.mark.asyncio
    async def test_generate_slide_without_reference_support(self):
        """Test slide generation when provider doesn't support reference images."""
        # Create a provider that has generate_image but not reference methods
        class NoRefProvider(ImageProvider):
            def __init__(self):
                super().__init__(None)
                self._provider_name = "noref"
                self._model_name = "noref-model"

            @property
            def provider_name(self):
                return self._provider_name

            @property
            def model_name(self):
                return self._model_name

            def generate_image(self, prompt, ref_images=None, aspect_ratio="1:1", resolution="1K"):
                return Image.new('RGB', (1920, 1080), color=(200, 100, 100))

            def validate_connection(self):
                return True

            # Add minimal reference methods to avoid AttributeError
            def generate_first_slide(self, prompt, aspect_ratio="16:9", resolution="2K"):
                return self.generate_image(prompt, aspect_ratio=aspect_ratio, resolution=resolution)

            def generate_subsequent_slide(self, prompt, slide_number, aspect_ratio="16:9", resolution="2K"):
                return self.generate_image(prompt, aspect_ratio=aspect_ratio, resolution=resolution)

        tool = GenerateImageTool(image_provider=NoRefProvider())

        # Generate first slide
        result1 = await tool.execute(
            prompt="First slide",
            slide_number=1
        )
        assert result1.error is None

        # Generate second slide (should use fallback logic)
        result2 = await tool.execute(
            prompt="Second slide",
            slide_number=2
        )
        assert result2.error is None

    def test_get_reference_image(self, generate_image_tool, mock_image_provider):
        """Test retrieving the reference image."""
        # Initially no reference
        assert generate_image_tool.get_reference_image() is None

        # Set a reference on the provider
        test_image = Image.new('RGB', (100, 100), color=(255, 0, 0))
        mock_image_provider.reference_image = test_image

        # Should return the reference
        assert generate_image_tool.get_reference_image() == test_image

    def test_clear_reference(self, generate_image_tool, mock_image_provider):
        """Test clearing the reference image."""
        # Set a reference
        test_image = Image.new('RGB', (100, 100), color=(255, 0, 0))
        mock_image_provider.reference_image = test_image

        # Clear it
        generate_image_tool.clear_reference()

        # Should be None
        assert mock_image_provider.reference_image is None
        assert generate_image_tool.reference_image is None

    def test_tool_repr(self, mock_image_provider):
        """Test string representation of the tool."""
        tool = GenerateImageTool(image_provider=mock_image_provider)
        repr_str = repr(tool)
        assert "GenerateImageTool" in repr_str
        assert "MockImageProvider" in repr_str

    @pytest.mark.asyncio
    async def test_image_save_conversion(self, generate_image_tool, mock_image_provider):
        """Test that images are properly converted and saved."""
        # Create an RGBA image to test conversion
        rgba_image = Image.new('RGBA', (1920, 1080), color=(100, 150, 200, 128))
        mock_image_provider.generate_first_slide = Mock(return_value=rgba_image)

        # Use a specific output directory for testing
        test_output_dir = tempfile.mkdtemp()

        result = await generate_image_tool.execute(
            prompt="RGBA slide",
            slide_number=1,
            output_dir=test_output_dir
        )

        assert result.error is None
        expected_path = os.path.join(test_output_dir, "slide_001.png")
        assert os.path.exists(expected_path)

        # Verify the saved image is RGB (PNG can handle RGBA but we convert for consistency)
        saved_image = Image.open(expected_path)
        assert saved_image.mode == 'RGB'

        # Close the image to unlock file for deletion
        saved_image.close()

        # Cleanup
        shutil.rmtree(test_output_dir, ignore_errors=True)