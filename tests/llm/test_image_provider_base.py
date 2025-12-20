"""
Unit tests for ImageProvider base class.

These tests verify the abstract interface and common functionality.
"""

import pytest
from abc import ABC
from typing import Optional
from PIL import Image
from unittest.mock import MagicMock

# Import the base class
from src.agent_framework.llm.image_provider_base import ImageProvider


class ConcreteImageProvider(ImageProvider):
    """Concrete implementation of ImageProvider for testing."""

    def __init__(self, api_key=None):
        super().__init__(api_key=api_key)
        self._model_name = "test-model"

    @property
    def provider_name(self) -> str:
        return "test"

    @property
    def model_name(self) -> str:
        return self._model_name

    def generate_image(
        self,
        prompt: str,
        ref_images: Optional[List[Image.Image]] = None,
        aspect_ratio: str = "1:1",
        resolution: str = "1K"
    ) -> Optional[Image.Image]:
        """Mock implementation for testing."""
        # Create a simple test image based on resolution
        if resolution == "1K":
            size = (1024, 1024)
        elif resolution == "2K":
            size = (2048, 2048)
        elif resolution == "4K":
            size = (4096, 4096)
        else:
            size = (1024, 1024)
        return Image.new('RGB', size, color='red')

    def validate_connection(self) -> bool:
        """Mock implementation for testing."""
        return True


class TestImageProviderBase:
    """Test cases for ImageProvider base class."""

    def test_inheritance(self):
        """Test that ImageProvider is an abstract base class."""
        assert issubclass(ImageProvider, ABC)

    def test_concrete_implementation(self):
        """Test that concrete implementation works correctly."""
        provider = ConcreteImageProvider(api_key="test_key")

        assert provider.provider_name == "test"
        assert provider.model_name == "test-model"
        assert provider.api_key == "test_key"

    def test_repr(self):
        """Test string representation."""
        provider = ConcreteImageProvider()
        repr_str = repr(provider)

        assert "ConcreteImageProvider" in repr_str
        assert "provider=test" in repr_str
        assert "model=test-model" in repr_str

    def test_generate_image_interface(self):
        """Test generate_image method interface."""
        provider = ConcreteImageProvider()

        image = provider.generate_image("Test prompt")
        assert isinstance(image, Image.Image)
        assert image.size == (1024, 1024)

    def test_generate_image_with_parameters(self):
        """Test generate_image with custom parameters."""
        provider = ConcreteImageProvider()

        image = provider.generate_image(
            "Test prompt",
            aspect_ratio="16:9",
            resolution="2K"
        )
        assert image.size == (2048, 2048)

    def test_generate_image_with_reference_images(self):
        """Test generate_image with reference images."""
        provider = ConcreteImageProvider()

        ref_images = [Image.new('RGB', (100, 100), color='blue')]
        image = provider.generate_image(
            "Test prompt",
            ref_images=ref_images,
            resolution="4K"
        )
        assert image.size == (4096, 4096)

    @pytest.mark.asyncio
    async def test_generate_images_batch(self):
        """Test batch image generation."""
        provider = ConcreteImageProvider()

        prompts = ["Prompt 1", "Prompt 2", "Prompt 3"]
        images = await provider.generate_images_batch(prompts)

        assert len(images) == 3
        for image in images:
            assert isinstance(image, Image.Image)

    def test_validate_connection_interface(self):
        """Test validate_connection method interface."""
        provider = ConcreteImageProvider()
        result = provider.validate_connection()
        assert result is True

    def test_get_supported_sizes_default(self):
        """Test default supported sizes."""
        provider = ConcreteImageProvider()
        sizes = provider.get_supported_sizes()

        assert isinstance(sizes, list)
        assert len(sizes) > 0
        assert (1024, 1024) in sizes
        assert (1920, 1080) in sizes

    def test_get_supported_styles_default(self):
        """Test default supported styles."""
        provider = ConcreteImageProvider()
        styles = provider.get_supported_styles()

        assert isinstance(styles, list)
        assert len(styles) > 0
        assert "natural" in styles
        assert "vivid" in styles

    def test_abstract_methods(self):
        """Test that abstract methods must be implemented."""
        # This should fail because we're not implementing all abstract methods
        class IncompleteProvider(ImageProvider):
            def __init__(self):
                pass  # Not calling super().__init__()

        with pytest.raises(TypeError):
            IncompleteProvider()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])