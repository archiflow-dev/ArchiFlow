"""
OpenAI Image Provider for PPT Agent MVP.

Provides image generation capabilities using OpenAI's models:
- gpt-image-1.5: Native support for reference images and advanced reasoning
- DALL-E 3: High-quality image generation with text prompts

Supports reference-based generation for consistent styling across slides.
"""

import os
import logging
import base64
import io
from typing import Optional, List, Dict, Any
from PIL import Image
from ..config.env_loader import load_env

# Set up logger for this module
logger = logging.getLogger(__name__)

try:
    import openai
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    openai = None
    OpenAI = None

from .image_provider_base import ImageProvider

# Load environment variables
load_env()

class OpenAIImageProvider(ImageProvider):
    """OpenAI image provider for MVP with reference image support.

    Supports both gpt-image-1.5 and DALL-E models for different use cases:
    - gpt-image-1.5: Better understanding of complex prompts and reference images
    - DALL-E 3: Optimized for creative image generation from text
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        model: str = "gpt-image-1.5",
        timeout: int = 120
    ):
        """
        Initialize the OpenAI Image Provider.

        Args:
            api_key: OpenAI API key. If None, will try to get from environment.
            api_base: Optional custom API base URL. If None, uses default OpenAI endpoint.
            model: Model name to use for image generation (default: "gpt-image-1.5").
            timeout: Timeout for API requests in seconds (default: 120).
        """
        if not OPENAI_AVAILABLE:
            raise ImportError(
                "openai package is required. "
                "Install with: pip install openai"
            )

        # Initialize base class
        super().__init__(api_key=api_key)

        # Handle API key
        self.api_key = self.api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key is required. Set OPENAI_API_KEY environment variable "
                "or pass api_key parameter."
            )

        # Store model and other settings
        self._model_name = model
        self.timeout = timeout

        # Initialize OpenAI client
        try:
            client_kwargs = {"api_key": self.api_key}
            if api_base:
                client_kwargs["base_url"] = api_base
                logger.info(f"Using custom API base URL: {api_base}")

            self.client = OpenAI(**client_kwargs)
            self.reference_image = None  # First slide image for consistency
            self.reference_description = None  # Text description of reference style
            logger.info(f"OpenAI Image Provider initialized with model: {self._model_name}")
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            raise RuntimeError(f"Failed to connect to OpenAI API: {e}")

    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return "openai"

    @property
    def model_name(self) -> str:
        """Return the model name."""
        return self._model_name

    def __repr__(self):
        """String representation of the provider."""
        return f"OpenAIImageProvider(model={self.model_name}, has_reference={self.reference_image is not None})"

    def generate_image(
        self,
        prompt: str,
        ref_images: Optional[List[Image.Image]] = None,
        aspect_ratio: str = "16:9",
        resolution: str = "1024x1024"
    ) -> Optional[Image.Image]:
        """
        Generate image using OpenAI API (gpt-image-1.5 or DALL-E models)

        Args:
            prompt: The image generation prompt
            ref_images: Optional list of reference images (gpt-image-1.5 supports image references)
            aspect_ratio: Image aspect ratio (e.g., "16:9", "1:1", "9:16")
            resolution: Image resolution (e.g., "1024x1024", "1792x1024", "1024x1792")

        Returns:
            Generated PIL Image object, or None if failed
        """
        try:
            # For gpt-image-1.5, we can handle reference images directly
            if self.model_name == "gpt-image-1.5":
                return self._generate_with_gpt_image(prompt, ref_images, aspect_ratio, resolution)
            else:
                # Fallback to DALL-E style generation for other models
                return self._generate_with_dalle_style(prompt, ref_images, aspect_ratio, resolution)

        except Exception as e:
            error_detail = f"Error generating image with OpenAI: {type(e).__name__}: {str(e)}"
            logger.error(error_detail, exc_info=True)
            raise Exception(error_detail) from e

    def _generate_with_gpt_image(
        self,
        prompt: str,
        ref_images: Optional[List[Image.Image]],
        aspect_ratio: str,
        resolution: str
    ) -> Optional[Image.Image]:
        """
        Generate image using gpt-image-1.5 with native support for reference images.
        """
        # Prepare the message content
        messages = [{"role": "user", "content": []}]

        # Add reference images if provided (gpt-image-1.5 supports this)
        if ref_images:
            for ref_img in ref_images:
                # Convert PIL Image to base64
                buffered = io.BytesIO()
                ref_img.save(buffered, format="PNG")
                img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

                messages[0]["content"].append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{img_base64}",
                        "detail": "high"
                    }
                })

        # Add text prompt
        messages[0]["content"].append({
            "type": "text",
            "text": prompt
        })

        logger.debug(f"Calling gpt-image-1.5 API with {len(ref_images) if ref_images else 0} reference images")

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            max_tokens=1000,
            temperature=0.7,
            # gpt-image-1.5 specific parameters
            response_format={"type": "image"}
        )

        logger.debug("gpt-image-1.5 API call completed")

        if not response.choices:
            raise ValueError("No choices in API response")

        # Extract image from response (gpt-image-1.5 might return images differently)
        choice = response.choices[0]
        if hasattr(choice.message, 'content') and choice.message.content:
            # If the content is a base64 image
            if choice.message.content.startswith('data:image'):
                # Extract base64 data
                import re
                base64_match = re.search(r'base64,(.*)', choice.message.content)
                if base64_match:
                    img_data = base64.b64decode(base64_match.group(1))
                    return Image.open(io.BytesIO(img_data))

        raise ValueError("No valid image found in gpt-image-1.5 response")

    def _generate_with_dalle_style(
        self,
        prompt: str,
        ref_images: Optional[List[Image.Image]],
        aspect_ratio: str,
        resolution: str
    ) -> Optional[Image.Image]:
        """
        Generate image using DALL-E style API (for backward compatibility).
        """
        # Enhanced prompt with style guidance if we have a reference
        enhanced_prompt = self._enhance_prompt_with_reference(prompt, ref_images)

        # Map aspect ratio to OpenAI size
        size = self._map_resolution_to_size(resolution, aspect_ratio)

        logger.debug(f"Calling OpenAI API for image generation...")
        logger.debug(f"Config - model: {self.model_name}, size: {size}")

        response = self.client.images.generate(
            model=self.model_name,
            prompt=enhanced_prompt,
            n=1,
            size=size,
            quality="standard",  # Can be "standard" or "hd"
            response_format="url"  # Get URL for better quality
        )

        logger.debug("OpenAI API call completed")

        if not response.data:
            raise ValueError("No image data in API response")

        # Get the image URL
        image_url = response.data[0].url
        if not image_url:
            raise ValueError("No image URL in API response")

        # Download and convert to PIL Image
        import requests
        img_response = requests.get(image_url, timeout=30)
        img_response.raise_for_status()

        image = Image.open(io.BytesIO(img_response.content))
        logger.debug(f"Successfully downloaded and converted image to PIL")

        return image

    def _enhance_prompt_with_reference(
        self,
        prompt: str,
        ref_images: Optional[List[Image.Image]] = None
    ) -> str:
        """
        Enhance the prompt with reference style information.

        Since DALL-E 3 doesn't directly accept image references, we enhance the prompt
        with textual descriptions of the desired style.
        """
        if self.reference_description and (ref_images or self.reference_image):
            # We have a reference style to maintain
            enhanced = f"""
Create a professional presentation slide image with the following exact style specifications:
{self.reference_description}

CONTENT TO CREATE:
{prompt}

CRITICAL REQUIREMENTS:
- Match the exact visual style, color palette, lighting, and mood described above
- Maintain consistent composition approach and artistic treatment
- Use identical design language and visual elements
- Only change the subject matter as specified in CONTENT TO CREATE
- This is slide #{getattr(self, '_slide_counter', 1)} in a consistent presentation series
"""
            # Increment slide counter for tracking
            self._slide_counter = getattr(self, '_slide_counter', 1) + 1
            return enhanced.strip()

        # No reference style, use standard presentation enhancement
        return f"""
Professional presentation slide image.
{prompt}
Clean, modern design, suitable for business presentation.
Minimalist aesthetic with clear visual hierarchy.
Consistent color palette and professional typography.
"""

    def _map_resolution_to_size(self, resolution: str, aspect_ratio: str) -> str:
        """
        Map resolution and aspect ratio to OpenAI's supported sizes.

        DALL-E 3 supports: 1024x1024, 1792x1024, 1024x1792
        """
        # Extract dimensions from resolution string
        if 'x' in resolution:
            # Already in the correct format
            return resolution

        # Map based on aspect ratio
        if aspect_ratio == "16:9":
            return "1792x1024"  # Landscape
        elif aspect_ratio == "9:16":
            return "1024x1792"  # Portrait
        else:
            return "1024x1024"  # Default square

    def get_supported_sizes(self) -> list[tuple[int, int]]:
        """
        Get list of supported image dimensions for OpenAI models.

        Returns:
            List of (width, height) tuples
        """
        # Supported sizes vary by model
        if self.model_name == "gpt-image-1.5":
            # gpt-image-1.5 supports more flexible sizes
            return [
                (512, 512),
                (1024, 1024),
                (1536, 1536),
                (1792, 1024),  # Landscape (16:9)
                (1024, 1792),  # Portrait (9:16)
                (2048, 2048),
            ]
        else:
            # DALL-E 3 specific supported sizes
            return [
                (1024, 1024),  # Square
                (1792, 1024),  # Landscape (16:9)
                (1024, 1792),  # Portrait (9:16)
            ]

    def get_supported_styles(self) -> list[str]:
        """
        Get list of supported styles for OpenAI models.

        Returns:
            List of style identifiers
        """
        # Styles vary by model
        if self.model_name == "gpt-image-1.5":
            # gpt-image-1.5 supports more nuanced styles through prompts
            return [
                "natural", "vivid", "photorealistic", "digital-art", "presentation",
                "minimalist", "corporate", "educational", "artistic", "technical"
            ]
        else:
            # DALL-E 3 specific styles (uses quality parameter)
            return ["natural", "vivid", "hd", "presentation"]

    def validate_connection(self) -> bool:
        """
        Validate connection to OpenAI API.

        Returns:
            True if connection is valid.

        Raises:
            RuntimeError: If connection fails.
        """
        try:
            # Try a simple API call to validate connection
            response = self.client.models.list()

            # Check for the specific model we're using
            if self.model_name == "gpt-image-1.5":
                # Look for gpt-image models
                matching_models = [m for m in response.data if "gpt-image" in m.id.lower()]
                model_type = "GPT-Image"
            else:
                # Look for DALL-E models
                matching_models = [m for m in response.data if "dall-e" in m.id.lower()]
                model_type = "DALL-E"

            if not matching_models:
                logger.warning(f"No {model_type} models found for this API key")
                # Check if our specific model is available
                available_models = [m.id for m in response.data]
                if self.model_name in available_models:
                    logger.info(f"Model {self.model_name} is available")
                    return True
                elif response.data:
                    logger.info(f"Found {len(response.data)} models but no {model_type} models")
                    logger.debug(f"Available models: {available_models}")
                return False

            logger.info(f"Connection validated. Found {len(matching_models)} {model_type} models")
            return True

        except Exception as e:
            logger.error(f"Failed to validate OpenAI API connection: {e}")
            raise RuntimeError(f"Cannot connect to OpenAI API: {e}")

    def generate_first_slide(self, prompt: str, *, aspect_ratio: str = "16:9", resolution: str = "1792x1024") -> Image.Image:
        """
        Generate the first slide - establishes the visual style for all slides.

        Args:
            prompt: Text description of the slide image
            aspect_ratio: Image aspect ratio (default: "16:9" for presentations)
            resolution: Image resolution (default: "1792x1024" for DALL-E 3)

        Returns:
            Generated image as PIL Image object
        """
        enhanced_prompt = f"""
Create a professional presentation slide image that will establish the visual style for an entire presentation.

STYLE REQUIREMENTS:
- Clean, modern, professional business presentation aesthetic
- Consistent color palette (use 2-3 primary colors harmoniously)
- Soft, professional lighting with subtle shadows
- Minimalist design with clear visual hierarchy
- Sans-serif typography styling
- Subtle gradients or flat design elements
- Corporate/educational presentation style

CONTENT:
{prompt}

This slide will define the visual style for all subsequent slides in the presentation.
"""

        image = self.generate_image(
            prompt=enhanced_prompt,
            aspect_ratio=aspect_ratio,
            resolution=resolution
        )

        if image:
            # Store as reference for all subsequent slides
            self.reference_image = image

            # Also store a textual description for style consistency
            self.reference_description = """
VISUAL STYLE GUIDE:
- Clean, modern business presentation aesthetic
- Professional color palette with harmonious 2-3 color scheme
- Soft, even lighting with subtle professional shadows
- Minimalist composition with clear visual hierarchy
- Sans-serif typography style
- Either subtle gradients or flat design elements
- Corporate/educational presentation mood
- Consistent spacing and alignment
- Professional, polished appearance
"""
            self._slide_counter = 1
            logger.info("First slide generated and stored as reference")

        return image

    def generate_subsequent_slide(
        self,
        prompt: str,
        slide_number: int,
        *,
        aspect_ratio: str = "16:9",
        resolution: str = "1792x1024"
    ) -> Image.Image:
        """
        Generate subsequent slides using first slide as style reference.

        Args:
            prompt: Text description of the slide image
            slide_number: The slide number (for logging)
            aspect_ratio: Image aspect ratio (default: "16:9" for presentations)
            resolution: Image resolution (default: "1792x1024" for DALL-E 3)

        Returns:
            Generated image as PIL Image object
        """
        if not self.reference_description:
            # Fallback: treat as first slide
            logger.warning("No reference style available, generating first slide")
            return self.generate_first_slide(
                prompt,
                aspect_ratio=aspect_ratio,
                resolution=resolution
            )

        # Set the slide counter for the enhanced prompt
        self._slide_counter = slide_number

        # Pass reference image to maintain consistency
        ref_images = [self.reference_image] if self.reference_image else None

        image = self.generate_image(
            prompt=prompt,
            ref_images=ref_images,
            aspect_ratio=aspect_ratio,
            resolution=resolution
        )

        return image


# For backward compatibility and testing
MockImageProvider = OpenAIImageProvider