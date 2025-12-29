"""
Generate Comic Panel Tool for Comic Agent.

This tool generates images for comic book panels using the configured
image provider (Google Image Provider by default). It handles panel numbering,
character references, and establishes consistent character appearance across panels.
"""

import os
import logging
from typing import Optional, Dict, Any, List
from pathlib import Path
from PIL import Image
from pydantic import Field

from ..tool_base import BaseTool, ToolResult
from ...llm.image_provider_base import ImageProvider
from ...llm.google_image_provider import GoogleImageProvider

# Set up logger for this module
logger = logging.getLogger(__name__)


class GenerateComicPanelTool(BaseTool):
    """
    Tool for generating comic book panel images.

    This tool uses an image provider to generate images for comic panels.
    It supports character reference images for consistent character appearance
    across all panels in the comic.
    """

    name: str = "generate_comic_panel"
    description: str = "Generate an image for a comic book panel or character reference sheet."

    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Text description of the panel or character to generate"
            },
            "panel_type": {
                "type": "string",
                "enum": ["character_reference", "establishing_shot", "action", "dialogue", "close_up", "transition"],
                "description": "Type of panel: character_reference (for character sheets), establishing_shot, action, dialogue, close_up, or transition"
            },
            "page_number": {
                "type": "integer",
                "description": "Page number (1-based, not needed for character references)",
                "minimum": 1
            },
            "panel_number": {
                "type": "integer",
                "description": "Panel number within the page (1-based, not needed for character references)",
                "minimum": 1
            },
            "character_names": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Names of characters appearing in this panel"
            },
            "dialogue": {
                "type": "string",
                "description": "Dialogue or text to be shown in the panel"
            },
            "action": {
                "type": "string",
                "description": "Action happening in the panel"
            },
            "visual_details": {
                "type": "string",
                "description": "Detailed visual description (composition, lighting, mood, camera angle)"
            },
            "character_reference": {
                "type": "string",
                "description": "Character name to use as reference (loads from character_refs/ directory)"
            },
            "session_id": {
                "type": "string",
                "description": "Session ID for organizing images (default: 'default')"
            },
            "output_dir": {
                "type": "string",
                "description": "Output directory (default: data/sessions/{session_id}/panels or character_refs)"
            },
            "aspect_ratio": {
                "type": "string",
                "description": "Image aspect ratio",
                "enum": ["1:1", "16:9", "9:16", "4:3", "3:4"],
                "default": "4:3"
            },
            "resolution": {
                "type": "string",
                "description": "Image resolution",
                "enum": ["1K", "2K", "4K"],
                "default": "2K"
            }
        },
        "required": ["prompt", "panel_type"]
    }

    image_provider: Optional[ImageProvider] = Field(default=None, exclude=True)
    character_references: Dict[str, Image.Image] = Field(default_factory=dict, exclude=True)

    def __init__(self, image_provider: Optional[ImageProvider] = None, **data):
        """
        Initialize the GenerateComicPanelTool.

        Args:
            image_provider: Image provider to use for generation. If None, creates Google provider.
        """
        # Set image_provider in the data before calling super().__init__
        if image_provider is not None:
            data['image_provider'] = image_provider
        elif 'image_provider' not in data:
            google_api_key = os.getenv("GOOGLE_API_KEY")
            if not google_api_key:
                logger.warning("GOOGLE_API_KEY not found in environment. Image generation may fail.")
            try:
                data['image_provider'] = GoogleImageProvider(api_key=google_api_key)
            except Exception as e:
                logger.error(f"Failed to initialize Google Image Provider: {e}")
                data['image_provider'] = None

        # Initialize character references dict
        if 'character_references' not in data:
            data['character_references'] = {}

        super().__init__(**data)

    def _build_comic_prompt(
        self,
        prompt: str,
        panel_type: str,
        character_names: Optional[List[str]] = None,
        dialogue: Optional[str] = None,
        action: Optional[str] = None,
        visual_details: Optional[str] = None,
        page_number: Optional[int] = None,
        panel_number: Optional[int] = None
    ) -> str:
        """
        Build an enhanced prompt for comic panel generation.

        Args:
            prompt: Basic description
            panel_type: Type of panel
            character_names: Characters in the panel
            dialogue: Dialogue text
            action: Action description
            visual_details: Visual composition details
            page_number: Page number
            panel_number: Panel number

        Returns:
            Enhanced prompt for image generation
        """
        parts = []

        # Add panel type context
        if panel_type == "character_reference":
            parts.append("Character Reference Sheet: Full-body character design with consistent features.")
        else:
            parts.append(f"Comic Book Panel - {panel_type.replace('_', ' ').title()}")

        # Add main prompt
        parts.append(f"Scene: {prompt}")

        # Add character information
        if character_names and len(character_names) > 0:
            chars = ", ".join(character_names)
            parts.append(f"Characters: {chars}")

        # Add action if provided
        if action:
            parts.append(f"Action: {action}")

        # Add dialogue context (not rendered, just for composition)
        if dialogue:
            parts.append(f"Dialogue (for composition): {dialogue}")

        # Add visual details
        if visual_details:
            parts.append(f"Visual Details: {visual_details}")

        # Add panel context
        if page_number and panel_number:
            parts.append(f"Context: Page {page_number}, Panel {panel_number} of a comic book")

        # Add panel type-specific guidance
        panel_guidance = {
            "establishing_shot": "Wide shot establishing the scene and setting. Show full environment.",
            "action": "Dynamic composition showing movement and energy. Clear action lines.",
            "dialogue": "Character-focused composition. Characters positioned for speech bubbles.",
            "close_up": "Tight framing on character face or important detail. Emotional emphasis.",
            "transition": "Bridge between scenes. May show passage of time or location change."
        }

        if panel_type in panel_guidance:
            parts.append(f"Composition: {panel_guidance[panel_type]}")

        # Add comic book style guidance
        parts.append("Style: Comic book art with clear lines, bold colors, and dramatic composition.")

        return "\n\n".join(parts)

    async def execute(
        self,
        prompt: str,
        panel_type: str,
        session_id: str = "default",
        page_number: Optional[int] = None,
        panel_number: Optional[int] = None,
        character_names: Optional[List[str]] = None,
        dialogue: Optional[str] = None,
        action: Optional[str] = None,
        visual_details: Optional[str] = None,
        character_reference: Optional[str] = None,
        output_dir: Optional[str] = None,
        aspect_ratio: str = "4:3",
        resolution: str = "2K",
        **kwargs
    ) -> ToolResult:
        """
        Generate an image for a comic panel or character reference.

        Args:
            prompt: Text description of the panel or character to generate
            panel_type: Type of panel (character_reference, establishing_shot, action, dialogue, close_up, transition)
            session_id: Session ID for organizing images
            page_number: Page number (1-based, not needed for character references)
            panel_number: Panel number within the page (1-based, not needed for character references)
            character_names: Names of characters appearing in this panel
            dialogue: Dialogue or text to be shown in the panel
            action: Action happening in the panel
            visual_details: Detailed visual description (composition, lighting, mood, camera angle)
            character_reference: Character name to use as reference
            output_dir: Output directory (default: auto-determined)
            aspect_ratio: Image aspect ratio (default: "4:3")
            resolution: Image resolution (default: "2K")

        Returns:
            ToolResult containing the image path or error message
        """
        if not self.image_provider:
            return self.fail_response(
                "No image provider available. Please configure GOOGLE_API_KEY."
            )

        # Build enhanced prompt
        enhanced_prompt = self._build_comic_prompt(
            prompt=prompt,
            panel_type=panel_type,
            character_names=character_names,
            dialogue=dialogue,
            action=action,
            visual_details=visual_details,
            page_number=page_number,
            panel_number=panel_number
        )

        try:
            logger.info(f"Generating {panel_type} image")
            logger.debug(f"Enhanced prompt length: {len(enhanced_prompt)} characters")

            # Load character reference if specified
            ref_images = []
            if character_reference and character_reference in self.character_references:
                ref_images.append(self.character_references[character_reference])
                logger.info(f"Using character reference: {character_reference}")

            # Generate image
            image = self.image_provider.generate_image(
                prompt=enhanced_prompt,
                aspect_ratio=aspect_ratio,
                resolution=resolution,
                ref_images=ref_images if ref_images else None
            )

            if not image:
                return self.fail_response("Failed to generate image")

            # Determine output directory based on panel type
            if output_dir is None:
                if panel_type == "character_reference":
                    output_dir = os.path.join("data", "sessions", session_id, "character_refs")
                else:
                    output_dir = os.path.join("data", "sessions", session_id, "panels")

            # Create output directory
            os.makedirs(output_dir, exist_ok=True)

            # Generate filename
            if panel_type == "character_reference":
                # Use character name from prompt or default
                char_name = character_names[0] if character_names else "character"
                filename = f"{char_name.upper()}.png"
            else:
                # Panel file naming
                if not page_number or not panel_number:
                    return self.fail_response(
                        "page_number and panel_number are required for non-character_reference panels"
                    )
                filename = f"page_{page_number:02d}_panel_{panel_number:02d}.png"

            filepath = os.path.join(output_dir, filename)

            # Handle different image types
            if hasattr(image, '_pil_image'):
                pil_image = image._pil_image
            elif hasattr(image, 'mode'):
                pil_image = image
            else:
                return self.fail_response(f"Unsupported image type: {type(image)}")

            # Convert to RGB if necessary
            if pil_image.mode in ('RGBA', 'LA', 'P'):
                rgb_image = Image.new('RGB', pil_image.size, (255, 255, 255))
                if pil_image.mode == 'P':
                    pil_image = pil_image.convert('RGBA')
                rgb_image.paste(pil_image, mask=pil_image.split()[-1] if pil_image.mode in ('RGBA', 'LA') else None)
                pil_image = rgb_image

            # Save the image
            pil_image.save(filepath, 'PNG')
            logger.info(f"Image saved to: {filepath}")

            # Store character reference if it's a reference sheet
            if panel_type == "character_reference" and character_names:
                self.character_references[character_names[0]] = pil_image
                logger.info(f"Stored character reference: {character_names[0]}")

            # Return success
            result = {
                "success": True,
                "file_path": filepath,
                "filename": filename,
                "panel_type": panel_type,
                "session_id": session_id,
                "output_dir": output_dir,
                "image_size": pil_image.size
            }

            if panel_type == "character_reference":
                result["message"] = f"Character reference generated: {character_names[0] if character_names else 'unknown'}"
            else:
                result["message"] = f"Panel generated: Page {page_number}, Panel {panel_number}"
                result["page_number"] = page_number
                result["panel_number"] = panel_number

            return self.success_response(result)

        except Exception as e:
            error_msg = f"Error generating comic panel: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return self.fail_response(error_msg)

    def get_character_reference(self, character_name: str) -> Optional[Image.Image]:
        """
        Get stored character reference image.

        Args:
            character_name: Name of the character

        Returns:
            Character reference image if exists, None otherwise
        """
        return self.character_references.get(character_name)

    def clear_references(self):
        """Clear all stored character references."""
        self.character_references.clear()
        logger.info("Character references cleared")

    def __repr__(self):
        """String representation of the tool."""
        return f"GenerateComicPanelTool(provider={self.image_provider.__class__.__name__ if self.image_provider else None})"
