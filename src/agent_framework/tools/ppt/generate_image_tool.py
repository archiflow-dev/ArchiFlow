"""
Generate Image Tool for PPT Agent MVP.

This tool generates images for presentation slides using the configured
image provider (Google Image Provider by default). It handles slide numbering
and establishes reference images for consistent styling across slides.
"""

import os
import logging
from typing import Optional, Dict, Any
from PIL import Image

from ..tool_base import BaseTool, ToolResult
from ...llm.image_provider_base import ImageProvider
from ...llm.google_image_provider import GoogleImageProvider

# Set up logger for this module
logger = logging.getLogger(__name__)


class GenerateImageTool(BaseTool):
    """
    Tool for generating images for presentation slides.

    This tool uses an image provider to generate images for slides.
    It supports reference-based generation for consistent styling
    across multiple slides in a presentation.
    """

    name: str = "generate_image"
    description: str = "Generate an image for a presentation slide. The first slide establishes the visual style reference."

    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Text description of the slide image to generate"
            },
            "slide_number": {
                "type": "integer",
                "description": "Slide number (1-based). Slide 1 establishes reference style.",
                "minimum": 1
            },
            "session_id": {
                "type": "string",
                "description": "Session ID for organizing images (default: 'default')"
            },
            "output_dir": {
                "type": "string",
                "description": "Output directory for images (default: data/images/{session_id})"
            },
            "aspect_ratio": {
                "type": "string",
                "description": "Image aspect ratio",
                "enum": ["1:1", "16:9", "9:16"],
                "default": "16:9"
            },
            "resolution": {
                "type": "string",
                "description": "Image resolution",
                "enum": ["1K", "2K", "4K"],
                "default": "2K"
            }
        },
        "required": ["prompt", "slide_number"]
    }

    image_provider: Optional[ImageProvider] = None
    reference_image: Optional[Image.Image] = None

    def __init__(self, image_provider: Optional[ImageProvider] = None, **data):
        """
        Initialize the GenerateImageTool.

        Args:
            image_provider: Image provider to use for generation. If None, creates Google provider.
        """
        # Set image_provider in the data before calling super().__init__
        if image_provider is not None:
            data['image_provider'] = image_provider
        elif 'image_provider' not in data:
            # Only create default provider if not explicitly set to None
            google_api_key = os.getenv("GOOGLE_API_KEY")
            if not google_api_key:
                logger.warning("GOOGLE_API_KEY not found in environment. Image generation may fail.")
            try:
                data['image_provider'] = GoogleImageProvider(api_key=google_api_key)
            except Exception as e:
                logger.error(f"Failed to initialize Google Image Provider: {e}")
                data['image_provider'] = None

        super().__init__(**data)

    async def execute(
        self,
        prompt: str,
        slide_number: int,
        session_id: str = "default",
        output_dir: Optional[str] = None,
        aspect_ratio: str = "16:9",
        resolution: str = "2K",
        **kwargs
    ) -> ToolResult:
        """
        Generate an image for a presentation slide.

        Args:
            prompt: Text description of the image to generate
            slide_number: Slide number (1-based)
            session_id: Session ID for organizing images
            output_dir: Output directory for images (default: data/images/{session_id})
            aspect_ratio: Image aspect ratio (default: "16:9")
            resolution: Image resolution (default: "2K")

        Returns:
            ToolResult containing the image path or error message
        """
        if not self.image_provider:
            return self.fail_response(
                "No image provider available. Please configure GOOGLE_API_KEY or provide an image provider."
            )

        try:
            logger.info(f"Generating image for slide {slide_number}: {prompt}")

            # Generate image based on slide number
            if slide_number == 1:
                # First slide - establishes reference style
                logger.info("Generating first slide (reference image)")
                image = self.image_provider.generate_first_slide(
                    prompt=prompt,
                    aspect_ratio=aspect_ratio,
                    resolution=resolution
                )
                if image:
                    self.reference_image = image
                    logger.info("First slide generated and stored as reference")
            else:
                # Subsequent slides - use reference for consistency
                if hasattr(self.image_provider, 'generate_subsequent_slide'):
                    logger.info(f"Generating slide {slide_number} using reference style")
                    image = self.image_provider.generate_subsequent_slide(
                        prompt=prompt,
                        slide_number=slide_number,
                        aspect_ratio=aspect_ratio,
                        resolution=resolution
                    )
                else:
                    # Fallback for providers without reference support
                    logger.warning(f"Image provider doesn't support reference images, generating standalone image")
                    image = self.image_provider.generate_image(
                        prompt=f"Professional presentation slide #{slide_number}: {prompt}",
                        aspect_ratio=aspect_ratio,
                        resolution=resolution,
                        ref_images=[self.reference_image] if self.reference_image else None
                    )

            if not image:
                return self.fail_response("Failed to generate image")

            # Determine output directory
            if output_dir is None:
                # Default to data/images/{session_id}
                output_dir = os.path.join("data", "images", session_id)

            # Create output directory if it doesn't exist
            os.makedirs(output_dir, exist_ok=True)

            # Save image with proper naming convention
            filename = f"slide_{slide_number:03d}.png"
            filepath = os.path.join(output_dir, filename)

            # Handle different image types (PIL Image vs Google Image)
            if hasattr(image, '_pil_image'):
                # Google's Image wrapper
                pil_image = image._pil_image
            elif hasattr(image, 'mode'):
                # Standard PIL Image
                pil_image = image
            else:
                logger.error(f"Unsupported image type: {type(image)}")
                return self.fail_response(f"Unsupported image type: {type(image)}")

            # Convert to RGB if necessary (for PNG compatibility)
            if pil_image.mode in ('RGBA', 'LA', 'P'):
                rgb_image = Image.new('RGB', pil_image.size, (255, 255, 255))
                if pil_image.mode == 'P':
                    pil_image = pil_image.convert('RGBA')
                rgb_image.paste(pil_image, mask=pil_image.split()[-1] if pil_image.mode in ('RGBA', 'LA') else None)
                pil_image = rgb_image

            # Save the image
            pil_image.save(filepath, 'PNG')
            logger.info(f"Image saved to: {filepath}")

            # Return success with file information
            result = {
                "success": True,
                "file_path": filepath,
                "filename": filename,
                "slide_number": slide_number,
                "session_id": session_id,
                "output_dir": output_dir,
                "image_size": pil_image.size,
                "has_reference": self.reference_image is not None
            }

            if slide_number == 1:
                result["message"] = "First slide generated and saved as reference"
            else:
                result["message"] = f"Slide {slide_number} generated with consistent styling"

            return self.success_response(result)

        except Exception as e:
            error_msg = f"Error generating image for slide {slide_number}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return self.fail_response(error_msg)

    def get_reference_image(self) -> Optional[Image.Image]:
        """
        Get the current reference image.

        Returns:
            The reference image if one exists, None otherwise
        """
        if hasattr(self.image_provider, 'reference_image'):
            return self.image_provider.reference_image
        return self.reference_image

    def clear_reference(self):
        """Clear the stored reference image."""
        if hasattr(self.image_provider, 'reference_image'):
            self.image_provider.reference_image = None
        self.reference_image = None
        logger.info("Reference image cleared")

    def __repr__(self):
        """String representation of the tool."""
        return f"GenerateImageTool(provider={self.image_provider.__class__.__name__ if self.image_provider else None})"