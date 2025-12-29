"""
Google Image Provider for PPT Agent MVP.

Provides image generation capabilities using Google's Gemini 3 Pro Image Preview model.
Supports reference-based generation for consistent styling across slides.
"""

import os
import logging
import tempfile
import base64
from typing import Optional, List
from PIL import Image
from ..config.env_loader import load_env

# Set up logger for this module
logger = logging.getLogger(__name__)



try:
    import google.genai as genai
    from google.genai import types
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False
    genai = None
    types = None

from .image_provider_base import ImageProvider

# Load environment variables
load_env()

class GoogleImageProvider(ImageProvider):
    """Google GenAI image provider for MVP with reference image support."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        model: str = "gemini-3-pro-image-preview"
    ):
        """
        Initialize the Google Image Provider.

        Args:
            api_key: Google API key. If None, will try to get from environment.
            api_base: Optional custom API base URL. If None, uses default Google endpoint.
            model: Model name to use for image generation (default: "gemini-3-pro-image-preview").
        """
        if not GOOGLE_AVAILABLE:
            raise ImportError(
                "google.genai package is required. "
                "Install with: pip install google.genai"
            )

        # Initialize base class
        super().__init__(api_key=api_key)

        # Handle API key
        self.api_key = self.api_key or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Google API key is required. Set GOOGLE_API_KEY environment variable "
                "or pass api_key parameter."
            )

        # Store model and API base
        self._model_name = model
        self.api_base = api_base

        # Initialize Google client
        try:
            client_kwargs = {"api_key": self.api_key}
            if self.api_base:
                if not types:
                    raise ImportError("google.genai.types not available")
                client_kwargs["http_options"] = types.HttpOptions(base_url=self.api_base)
                logging.info(f"Using custom API base URL: {self.api_base}")

            self.client = genai.Client(**client_kwargs)
            self.reference_image = None  # First slide image for consistency
            logging.info(f"Google Image Provider initialized with model: {self._model_name}")
        except Exception as e:
            logging.error(f"Failed to initialize Google client: {e}")
            raise RuntimeError(f"Failed to connect to Google API: {e}")

    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return "google"

    @property
    def model_name(self) -> str:
        """Return the model name."""
        return self._model_name

    def __repr__(self):
        """String representation of the provider."""
        return f"GoogleImageProvider(model={self.model_name}, has_reference={self.reference_image is not None})"

    def generate_image(
        self,
        prompt: str,
        ref_images: Optional[List[Image.Image]] = None,
        aspect_ratio: str = "16:9",
        resolution: str = "2K"
    ) -> Optional[Image.Image]:
        """
        Generate image using Google GenAI SDK

        Args:
            prompt: The image generation prompt
            ref_images: Optional list of reference images
            aspect_ratio: Image aspect ratio (e.g., "16:9", "1:1", "9:16")
            resolution: Image resolution (supports "1K", "2K", "4K")

        Returns:
            Generated PIL Image object, or None if failed
        """

        try:
            # Construct content payload with text prompt and images
            contents = [prompt]

            # Process reference images if provided
            if ref_images:
                logger.debug(f"Processing {len(ref_images)} reference images for generation")
                for i, img in enumerate(ref_images):
                    if img:
                        # Convert to PIL if it isn't already (though type hint says it is)
                        if not isinstance(img, Image.Image):
                            logger.warning(f"Reference image {i} is not a PIL Image, skipping")
                            continue
                        
                        contents.append(img)
                
                # Add instruction to use the reference images
                if len(contents) > 1:
                     logger.info(f"Using {len(contents)-1} reference images for generation")

            logger.debug(f"Calling GenAI API for image generation with {len(ref_images) if ref_images else 0} reference images...")
            logger.debug(f"Config - aspect_ratio: {aspect_ratio}, resolution: {resolution}")

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_modalities=['TEXT', 'IMAGE'],
                    image_config=types.ImageConfig(
                        aspect_ratio=aspect_ratio,
                        image_size=resolution
                    ),
                )
            )

            logger.debug("GenAI API call completed")

            # Check if response has parts
            if response.parts is None:
                error_msg = "API response has no parts (response.parts is None). "
                error_msg += "This may indicate an API error, rate limiting, or invalid request."
                logger.error(error_msg)
                raise ValueError(error_msg)

            # Extract image from response
            for i, part in enumerate(response.parts):
                if part.text is not None:
                    logger.debug(f"Part {i}: TEXT - {part.text[:100] if len(part.text) > 100 else part.text}")
                else:
                    try:
                        logger.debug(f"Part {i}: Attempting to extract image...")
                        image = part.as_image()
                        if image:
                            logger.debug(f"Successfully extracted image from part {i}")
                            return image
                    except Exception as e:
                        logger.debug(f"Part {i}: Failed to extract image - {str(e)}")

            # No image found in response
            error_msg = "No image found in API response. "
            if response.parts:
                error_msg += f"Response had {len(response.parts)} parts but none contained valid images."
            else:
                error_msg += "Response had no parts."

            raise ValueError(error_msg)

        except Exception as e:
            error_detail = f"Error generating image with GenAI: {type(e).__name__}: {str(e)}"
            logger.error(error_detail, exc_info=True)
            raise Exception(error_detail) from e

    def get_supported_sizes(self) -> list[tuple[int, int]]:
        """
        Get list of supported image dimensions for Google Gemini.

        Returns:
            List of (width, height) tuples
        """
        # Google Gemini specific supported sizes
        return [
            (1024, 1024),
            (1920, 1080),
            (1080, 1920),
            (1792, 1024),
            (1024, 1792),
        ]

    def get_supported_styles(self) -> list[str]:
        """
        Get list of supported styles for Google Gemini.

        Returns:
            List of style identifiers
        """
        # Google Gemini specific styles
        return ["natural", "vivid", "photorealistic", "digital-art", "presentation"]

    def validate_connection(self) -> bool:
        """
        Validate connection to Google API.

        Returns:
            True if connection is valid.

        Raises:
            RuntimeError: If connection fails.
        """
        try:
            # Try to list available models to validate connection
            models = self.client.models.list()
            gemini_models = [m for m in models if "gemini" in m.name.lower() and "image" in m.name.lower()]
            if not gemini_models:
                logging.warning("No Gemini image models found for this API key")
                # Check if any models are available at all
                if models:
                    logging.info(f"Found {len(models)} models but no image generation models")
                return False
            logging.info(f"Connection validated. Found {len(gemini_models)} Gemini image models")
            return True
        except Exception as e:
            logging.error(f"Failed to validate Google API connection: {e}")
            raise RuntimeError(f"Cannot connect to Google API: {e}")

    def generate_first_slide(self, prompt: str, *, aspect_ratio: str = "16:9", resolution: str = "2K") -> Image.Image:
        """
        Generate the first slide - establishes the visual style for all slides.

        Args:
            prompt: Text description of the slide image
            aspect_ratio: Image aspect ratio (default: "16:9" for presentations)
            resolution: Image resolution (default: "2K")

        Returns:
            Generated image as PIL Image object
        """
        enhanced_prompt = f"""
        Create a professional presentation slide with these specifications:

        Visual Content: {prompt}

        Design Guidelines:
        - Modern, clean business presentation aesthetic
        - Professional typography with excellent readability
        - Balanced composition with strategic use of negative space
        - Corporate-quality imagery appropriate for business settings
        - Cohesive color palette that can be replicated across slides
        - High impact visual that engages while maintaining professionalism

        Technical Requirements:
        - 300 DPI resolution for print quality
        - Consistent lighting and shadows
        - Scalable vector-like appearance where applicable
        - Clean edges and professional finishing
        - Style that can be consistently adapted for subsequent slides

        This first slide will establish the visual foundation for the entire presentation.
        """

        image = self.generate_image(
            prompt=enhanced_prompt,
            aspect_ratio=aspect_ratio,
            resolution=resolution
        )

        if image:
            # Store as reference for all subsequent slides
            self.reference_image = image
            logger.info("First slide generated and stored as reference")

        return image

    def generate_subsequent_slide(
        self,
        prompt: str,
        slide_number: int,
        *,
        aspect_ratio: str = "16:9",
        resolution: str = "2K"
    ) -> Image.Image:
        """
        Generate subsequent slides using first slide as style reference.

        Args:
            prompt: Text description of the slide image
            slide_number: The slide number (for logging)
            aspect_ratio: Image aspect ratio (default: "16:9" for presentations)
            resolution: Image resolution (default: "2K")

        Returns:
            Generated image as PIL Image object
        """
        if not self.reference_image:
            # Fallback: treat as first slide
            logger.warning("No reference image available, generating first slide")
            return self.generate_first_slide(
                prompt,
                aspect_ratio=aspect_ratio,
                resolution=resolution
            )

        enhanced_prompt = f"""
        Create slide #{slide_number} for a professional presentation, maintaining visual consistency with the established style.

        Slide Content: {prompt}

        Consistency Requirements:
        - Maintain the same visual style, color palette, and lighting as previous slides
        - Use consistent typography and layout principles
        - Keep the same level of professionalism and quality
        - Ensure smooth visual flow between slides
        - Preserve the established mood and tone

        Design Principles:
        - Professional business presentation standard
        - Clear visual hierarchy and readability
        - Balanced composition with appropriate white space
        - Cohesive with overall presentation theme
        - Engaging yet professional appearance

        This slide should feel like it belongs to the same presentation family
        while effectively communicating its unique content.
        """

        # Generate without reference image for now (due to API limitations)
        image = self.generate_image(
            prompt=enhanced_prompt,
            ref_images=None,  # Don't pass reference image due to API format requirements
            aspect_ratio=aspect_ratio,
            resolution=resolution
        )

        return image


# For backward compatibility and testing
MockImageProvider = GoogleImageProvider