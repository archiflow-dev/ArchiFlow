"""
Base class for all image providers.

This module defines the abstract interface that all image providers must implement.
It provides a consistent API for generating images regardless of the underlying provider.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, AsyncGenerator, List
from PIL import Image
import logging


class ImageProvider(ABC):
    """Abstract base class for all image providers."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the image provider.

        Args:
            api_key: API key for the provider. If None, will try to get from environment.
        """
        self.api_key = api_key
        self.logger = logging.getLogger(self.__class__.__name__)

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the name of the provider (e.g., 'google', 'openai')."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model name being used (e.g., 'gemini-3-pro-image-preview')."""
        pass

    @abstractmethod
    def generate_image(
        self,
        prompt: str,
        ref_images: Optional[list[Image.Image]] = None,
        aspect_ratio: str = "1:1",
        resolution: str = "1K"
    ) -> Optional[Image.Image]:
        """
        Generate an image from a text prompt.

        Args:
            prompt: Text description of the image to generate
            ref_images: Optional list of reference images for style consistency
            aspect_ratio: Image aspect ratio (e.g., '16:9', '1:1', '9:16')
            resolution: Image resolution (supports '1K', '2K', '4K')

        Returns:
            Generated image as PIL Image object, or None if failed

        Raises:
            RuntimeError: If image generation fails
            ValueError: If parameters are invalid
        """
        pass

    async def generate_images_batch(
        self,
        prompts: list[str],
        *,
        ref_images: Optional[list[Image.Image]] = None,
        aspect_ratio: str = "1:1",
        resolution: str = "1K"
    ) -> list[Image.Image]:
        """
        Generate multiple images from prompts.

        Default implementation generates images sequentially.
        Providers can override for parallel generation.

        Args:
            prompts: List of text descriptions
            ref_images: Optional list of reference images for all generations
            aspect_ratio: Image aspect ratio for all images
            resolution: Image resolution for all images

        Returns:
            List of generated images
        """
        images = []
        for prompt in prompts:
            image = self.generate_image(
                prompt=prompt,
                ref_images=ref_images,
                aspect_ratio=aspect_ratio,
                resolution=resolution
            )
            if image:
                images.append(image)
        return images

    @abstractmethod
    def validate_connection(self) -> bool:
        """
        Validate connection to the provider's API.

        Returns:
            True if connection is valid and API is accessible

        Raises:
            RuntimeError: If connection cannot be established
        """
        pass

    def get_supported_sizes(self) -> list[tuple[int, int]]:
        """
        Get list of supported image dimensions.

        Returns:
            List of (width, height) tuples
        """
        # Default common sizes - providers should override
        return [
            (1024, 1024),
            (1920, 1080),  # 16:9
            (1080, 1920),  # 9:16
            (1792, 1024),  # 16:9 (alternative)
            (1024, 1792),  # 9:16 (alternative)
        ]

    def get_supported_styles(self) -> list[str]:
        """
        Get list of supported styles.

        Returns:
            List of style identifiers
        """
        # Default styles - providers should override
        return ["natural", "vivid", "photorealistic", "digital-art"]

    def __repr__(self) -> str:
        """String representation of the provider."""
        return f"{self.__class__.__name__}(provider={self.provider_name}, model={self.model_name})"