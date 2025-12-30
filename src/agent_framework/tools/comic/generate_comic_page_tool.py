"""
Generate Comic Page Tool.

This tool generates a complete comic page from a comprehensive prompt
constructed by the comic agent.

SIMPLIFIED DESIGN (v2):
- Agent reads spec and constructs the full image generation prompt
- Tool just passes prompt to image AI
- No complex parameter extraction or mapping needed
"""

import os
import json
import logging
from typing import Optional, List, Dict, Any
from pathlib import Path
from pydantic import Field

from ..tool_base import BaseTool, ToolResult

try:
    from PIL import Image, ImageDraw
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

logger = logging.getLogger(__name__)


class GenerateComicPageTool(BaseTool):
    """
    Tool for generating a complete comic page.

    Simplified design: accepts a comprehensive prompt constructed by the agent.
    The agent reads the comic spec and constructs a detailed prompt that includes
    all layout, style, panel, and visual information.
    """

    name: str = "generate_comic_page"
    description: str = "Generate a complete comic page from a comprehensive prompt"

    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "session_id": {
                "type": "string",
                "description": "Session ID for organizing images"
            },
            "page_number": {
                "type": "integer",
                "description": "Page number (1-based)"
            },
            "page_prompt": {
                "type": "string",
                "description": "Complete image generation prompt including all layout, style, panel descriptions, colors, lighting, and visual details. The agent constructs this from the comic spec."
            },
            "characters": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of character names appearing on this page (for loading reference images)"
            },
            "aspect_ratio": {
                "type": "string",
                "description": "Aspect ratio for the page (default: '3:4' for portrait comic page)",
                "default": "3:4"
            }
        },
        "required": ["session_id", "page_number", "page_prompt"]
    }

    image_provider: Optional[Any] = Field(default=None, exclude=True)

    def __init__(self, image_provider: Optional[Any] = None, **data):
        """Initialize the GenerateComicPageTool."""
        if image_provider is not None:
            data['image_provider'] = image_provider
        elif 'image_provider' not in data:
            # Try to get from environment
            google_api_key = os.getenv("GOOGLE_API_KEY")
            if google_api_key:
                try:
                    from agent_framework.llm.google_image_provider import GoogleImageProvider
                    data['image_provider'] = GoogleImageProvider(api_key=google_api_key)
                except Exception as e:
                    logger.warning(f"Failed to initialize image provider: {e}")
                    data['image_provider'] = None

        super().__init__(**data)

    async def execute(
        self,
        session_id: str,
        page_number: int,
        page_prompt: str,
        characters: Optional[List[str]] = None,
        aspect_ratio: str = "3:4",
        **kwargs
    ) -> ToolResult:
        """
        Generate a complete comic page.

        Args:
            session_id: Session identifier for organizing output
            page_number: Page number (1-based)
            page_prompt: Complete image generation prompt (constructed by agent)
            characters: List of character names for loading reference images
            aspect_ratio: Aspect ratio (default '3:4' for portrait comic)

        Returns:
            ToolResult with page image path or error
        """
        if not PIL_AVAILABLE:
            return self.fail_response(
                "PIL (Pillow) is not installed. Install with: pip install Pillow"
            )

        if not self.image_provider:
            return self.fail_response(
                "No image provider available. Please configure GOOGLE_API_KEY."
            )

        try:
            # Setup output directory
            base_dir = os.path.join("data", "sessions", session_id)
            pages_dir = os.path.join(base_dir, "pages")
            logs_dir = os.path.join(pages_dir, "logs")
            os.makedirs(pages_dir, exist_ok=True)
            os.makedirs(logs_dir, exist_ok=True)

            page_filename = f"page_{page_number:02d}.png"
            page_path = os.path.join(pages_dir, page_filename)

            # Collect character reference images
            ref_images = []
            if characters:
                ref_dir = os.path.join(base_dir, "character_refs")
                for char_name in characters:
                    # Try case variations
                    for name in [char_name.upper(), char_name.lower(), char_name.title(), char_name]:
                        path = os.path.join(ref_dir, f"{name}.png")
                        if os.path.exists(path):
                            try:
                                img = Image.open(path)
                                ref_images.append(img)
                                logger.info(f"Loaded reference for {char_name}")
                                break
                            except Exception as e:
                                logger.warning(f"Failed to load ref for {char_name}: {e}")

            # Enhance prompt with reference instructions if we have references
            final_prompt = page_prompt
            if ref_images:
                final_prompt += "\n\nCRITICAL INSTRUCTION: Character reference images are attached. " \
                               "You MUST maintain strict visual consistency with these references. " \
                               "Match their facial features, clothing, and style exactly."

            # Log the generation request
            log_entry = {
                "timestamp": __import__('datetime').datetime.now().isoformat(),
                "session_id": session_id,
                "page_number": page_number,
                "aspect_ratio": aspect_ratio,
                "prompt_length": len(final_prompt),
                "prompt_preview": final_prompt[:500] + "..." if len(final_prompt) > 500 else final_prompt,
                "characters": characters or [],
                "reference_count": len(ref_images)
            }

            log_filename = f"gen_{__import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]}.json"
            log_path = os.path.join(logs_dir, log_filename)
            with open(log_path, 'w', encoding='utf-8') as f:
                json.dump(log_entry, f, indent=2, ensure_ascii=False)

            logger.info(f"Generating page {page_number} with aspect ratio {aspect_ratio}")
            logger.debug(f"Prompt preview: {final_prompt[:200]}...")

            # Generate the page image
            image = self.image_provider.generate_image(
                prompt=final_prompt,
                aspect_ratio=aspect_ratio,
                resolution="2K",
                ref_images=ref_images if ref_images else None,
                session_id=session_id,
                output_dir=pages_dir
            )

            # Handle PIL image
            if hasattr(image, '_pil_image'):
                pil_image = image._pil_image
            else:
                pil_image = image

            # Save the image
            pil_image.save(page_path, 'PNG', optimize=True)
            logger.info(f"Page saved to: {page_path}")

            # Get file size
            file_size = os.path.getsize(page_path) / (1024 * 1024)  # MB

            return self.success_response({
                "success": True,
                "page_path": page_path,
                "page_number": page_number,
                "file_size_mb": round(file_size, 2),
                "log_path": log_path
            })

        except Exception as e:
            logger.error(f"Page generation failed: {e}", exc_info=True)
            return self.fail_response(f"Page generation failed: {str(e)}")
